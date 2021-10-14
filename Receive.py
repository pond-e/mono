#!/usr/bin/env python
#encoding=utf-8

import threading
import time
import os
from serial import *
from optparse import *
from sys import stdout, stdin, stderr, exit
from PIL import Image

#	RaspberryPiでない場合はimportしない
try:
	import RPi.GPIO as GPIO
	IamRaspi = True
except ImportError:
	IamRaspi = False

from parseFmt_Binary import FmtBinary 
from transTools import *

# serial port object
ser = None

# parser
options = None
args = None

# others
thread = None		#	thread用	
rcvflag = False		#	受信処理を行っていればTrue 行っていなければFalse
address = 0x78		#	宛先(全子機宛)
bOnClose = False	#	クローズ処理を行ったか否か

# コマンドラインパラメータの解釈
#  -D : 送信宛先の指定 (デフォルトはブロードキャスト)
#  -b : ボーレート
#  -t : シリアルポートのデバイス
def ParseArgs():
	global options
	global args
	parser = OptionParser()
	parser.add_option('-b', '--baud', dest='baud', type='int',
					help='baud rate for serial connection.', metavar='BAUD', default=115200)
	parser.add_option('-t', '--target', type='string', help='target for connection', dest='target', default='/dev/ttyUSB0')
	(options, args) = parser.parse_args()

def ReadPayload( timeout=5 ):
	global ser
	fmt = FmtBinary()
	i = 0
	pay = []
	stime = time.time()
	while True:
		# バイナリ書式を解釈する
		try:
			c = ord(ser.read(1))
		# when time out
		except TypeError:
			fmt.terminate()
			ntime = time.time()
			if ntime-stime > timeout:
				pay = [0xFF]*4
				return pay
			else:
				continue

		fmt.process(c)
		if fmt.is_comp():
			pay = fmt.get_payload()
			fmt.terminate()
			break

	if len(pay) == 0:
		pay = [0xFF]*4

	return pay

# 読み出しを行う処理
def WrkReadSerial():
	send_byte = 200		#	一番速度が速かったものを採用
	old_num = -1
	data = []
	global rcvflag
	
	#	予想パケット数が通知されたときパケット数を記録する
	while True:
		pay = ReadPayload(10)
		if pay[2] == 0x01:
			#	全体のパケット数を記憶
			pkt_num = (pay[14]<<8) + pay[15]
			print(str(pkt_num) + " Packetes")
			break
		else :
			#	タイムアウト処理を入れたい
			rcvflag = 0
			print("Time out")
			return

	#	画像のパケットが送信されたときデータをリストに保存
	while True:
		pay = ReadPayload()
		if pay[2] == 0x02:
			now_num = (pay[14]<<8)+pay[15]
			if now_num == 0:
				stime = time.time()
			#	パケットが抜けたとき0で埋める
			if old_num != now_num-1:
				if now_num-old_num-1  >= 0:
					string = "\r" + str(now_num) + " " + str(now_num-old_num-1) + 'Packet lost\n'
					stderr.write( string )
					stderr.flush()
				i = 0
				num = send_byte
				while i < num*(now_num-old_num-1)  :
					data.append( 0x00 )
					i += 1
			if now_num-old_num-1  >= 0:
				#	データをリストに保存
				for a in pay[16:] :
					data.append(a)
				old_num = now_num

			#	進捗の表示
			prog = float(now_num)/pkt_num*100.0
			bar = ProgressBar( prog, 40 )
			string = "\r" + bar + " %2.2f%%" % prog
			stdout.write( string )
			stdout.flush()

			if now_num == pkt_num - 1:
				break
		else:
			#	タイムアウト処理を入れたい	
			rcvflag = 0
			print("Time out")
			return

	#	終了リクエストが来たときファイルを保存する
	while True:
		pay = ReadPayload()
		if pay[2] == 0x03:
			etime = time.time()-stime
			bar = ProgressBar( 100.0, 40 )
			print('\r' + bar + ' 100.00%')

			print("Save" + str(len(data)) + "Byte Data")
			print("Transmit Time : " + "%.2f" % etime + " Second")
			print("Transmit Speed : " + "%.2f" % float(len(data)/etime) + " Byte/Sec")
			#	ファイル名を連番にする
			rnumber = ReadFileNumber('recv.dat')

			#	ファイルを保存
			imgfile = 'img/recv' + str(rnumber).zfill(8) + '.jp2'
			f = open( imgfile, 'w' )
			for x in data :
				f.write( chr(x) )
			f.close()
			data = []

			#	写真を変換する
			print("Convert Photo")
			convertfile = 'img/recv' + str(rnumber).zfill(8) + '.jpg'
			cmd = 'convert ' + imgfile + ' ' + convertfile
			flag = os.system(cmd)
			if flag != 0:
				print("Can not convert. Please try again...")
			else :
				rnumber += 1
				f = open( 'recv.dat', 'w' )
				f.write(str(rnumber))
				f.close()
				im = Image.open(convertfile)
				im.show()
				print("Finish")
			rcvflag = 0
			break
		else:
			#	タイムアウト処理を入れたい	
			rcvflag = 0
			print("Time out")
			return

# 終了処理
def DoTerminate():
	global bOnClose, ser, thread
	bOnClose = True
	print("!TERMINATE")

	#	RaspberryPiの場合スレッドを消す
	if IamRaspi == True:
		try :
			thread.cancel()
		except:
			pass

	time.sleep(0.5)
	ser.close()
	exit(0)

#	GPIO入力待ち
def GPIO_Input():
	global ser
	global rcvflag
	#	入力に使うGPIOのポート番号
	IO_NO = 25

	#	設定
	try :	#	GPIOがない場合この関数を処理しない
		GPIO.setmode(GPIO.BCM)
	except NameError:
		return

	GPIO.setup(IO_NO, GPIO.IN, pull_up_down=GPIO.PUD_UP )

	while True:
		try:
			GPIO.wait_for_edge( IO_NO, GPIO.FALLING )
		except:
			#	一旦設定を消す
			GPIO.cleanup()
			#	再設定
			GPIO.setmode(GPIO.BCM)
			GPIO.setup(IO_NO, GPIO.IN, pull_up_down=GPIO.PUD_UP )
			#	下記の処理をせずにwhileの最初から
			continue

		if rcvflag == False:
			rcvflag = True
			GenerateImageRequest(address)
			rslt = AckWait(5)
			if rslt == 0x01:
				WrkReadSerial()
			else:
				print("Not Retrun ACK")
				rcvflag = False
				time.sleep(0.5)
		else :
			time.sleep(0.5)


if __name__=='__main__':
	### now in main thread
	os.system('clear')
	print('Welcome to Photograph Transfer Program!')
	print('Please press the button.')
	# parse command line arguments
	ParseArgs()
	
	# open serial port
	try:
		ser = OpenSerial(options.target, options.baud)
	except:
		exit(1)
		
	if ser == None: exit(1)
	if not ser.isOpen(): exit(1)
	
	# GPIO 入力(RaspberryPiの時だけ)
	if IamRaspi == True:
		thread=threading.Thread(target=GPIO_Input)
		thread.setDaemon(True)
		thread.start()
	
	# 入出力が tty ならキーボード入力を有効とする
	bInteractive = stdin.isatty() # and stdout.isatty()
	
	try:
		while True:				
			# 標準入力から何か入力する (Enter 入力が必要)
			if bInteractive:
				l = stdin.readline()
				if l[0] == 'q':
					DoTerminate()
				elif l[0] == 's':
					if rcvflag == False:
						rcvflag = True
						GenerateImageRequest( address )
						rslt = AckWait(5)
						if rslt == 0x01:
							WrkReadSerial()
						else:
							print("Not Retrun ACK")
							rcvflag = False
				else :
					print("Take photos : Please press the button.")
					print("Exit this program : Please input \"q\" key.")
	except:
		if not bOnClose:
			DoTerminate()
