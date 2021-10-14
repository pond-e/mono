#!/usr/bin/env python
#encoding=utf-8

import threading
import time
import os
import subprocess
import picamera
from binascii import *
from struct import pack
from serial import *
from optparse import *
from sys import stdout, stdin, stderr, exit
import Image
import sys

from parseFmt_Binary import FmtBinary 
from transTools import *

# serial port object
ser = None

# parser
options = None
args = None

# others
t1 = None
t2 = None

address = 0x00

bOnClose = False
sec0 = time.time()

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

# 読み出しを行うスレッド
def WrkReadSerial():
	# バイナリ書式を解釈する
	fmt = FmtBinary()
	send_byte = 200
	old_num = -1
	data = []
	global ser
	while True:
		try:
			c = ord(ser.read(1))
		# when time out
		except TypeError:
			fmt.terminate()
			continue

		fmt.process(c)
		if fmt.is_comp():
			pay = fmt.get_payload()
			fmt.terminate()
			
			#	送信リクエストが来たとき写真を撮って送る
			if len(pay) > 4 :
				if pay[2] == 0x00:
					os.system('clear')
					print("Send Photograph")

					#	データの中身を消す
					data = []
					if( len(data) != 0 ):
						del data[ 0: len(data) ]

					#	写真を撮る
					print("Take a Photo")
					#	ファイル名を連番にする
					number = ReadFileNumber("send.dat")
					
					#	写真を撮る
					imgfile = 'img/send' + str(number).zfill(8) + '.jpg'
					with picamera.PiCamera() as camera:
						camera.start_preview()
						time.sleep(1)
						camera.capture( imgfile )

					#	写真を変換する
					print("Convert Photo")
					convertfile = 'img/send' + str(number).zfill(8) + '.jp2'
					cmd = 'convert -geometry 480x360 -quality 30 ' + imgfile + ' ' + convertfile
					os.system(cmd)

					number += 1
					f = open( 'send.dat', 'w' )
					f.write(str(number))
					f.close()

					#	写真をロードする
					print("Reading Photo Data")
					f = open( convertfile, 'rb' )
					while True:
						buffer = hexlify( f.read(1) )
						if buffer == '':
							break
						data.append( int( buffer, 16 ) )
					print('Load ' + str(len(data)) + ' Byte Data')
					f.close()

					#	写真を分割したときに何パケット送信するかを相手に知らせる
					print("Divide Photo")
					pkt_num = len(data)/send_byte
					if( len(data) % send_byte > 0 ):
						pkt_num += 1
					GenerateAllPacketNumber( address, pkt_num )

					#	写真を送信する
					print("Send Packet")
					i = 0
					count = 0
					while len(data) > i:
						if i+send_byte > len(data):
							end = len(data)
						else :
							end = i+send_byte

						#	パケットの作成
						pkt = GenerateSendImage( i/send_byte, data, i, end )
						#	パケットの送信
						ser.write(pkt)

						#	ACKが失敗していたら再送信
						if AckWait() == 0x00:
							count += 1
							#	5回だめならばあきらめる
							if count != 5:
								continue
							else :
								print("Time out...")

						count = 0
						#	進捗の表示
						prog = float(i)/len(data)*100.0
						bar = ProgressBar( prog, 40 )
						string = "\r" + bar + " %2.2f%%" % prog
						sys.stdout.write( string )
						sys.stdout.flush()

						i += send_byte
						#	何かしらのタイミングで次のパケットを送信
						#time.sleep(sleep_time)

					bar = ProgressBar( 100.0, 40 )
					print('\r' + bar + ' 100.00%')

					#	終了パケットを送信
					print("Finish")
					while 1:
						GenerateEndRequest( address )
						if AckWait != 0x00:
							break

				else:
					print("Error.")
					print("Try agein...")

# 画像送信パターンの作成
def GenerateSendImage(i, image, start, end ):
	a = [ ]
	a.append(0xa5)
	a.append(0x5a)
	a.append(0x80)
	a.append(0xFF) # length
	a.append( address ) # extended
	a.append(0xA0) # extended
	a.append(0x02) # resp id
	a.append(0x01) # ack
	a.append(0x02) # resending
	a.append(0x0A) # once
	a.append(0xff) # option end
	a.append((i & 0xFF00) >> 8)	# payload 
	a.append(i & 0xFF)

	# image
	i = start
	while i < end :
		a.append( image[i] )
		i += 1

	# calc xor checksum
	xor = 0
	a[3] = len(a) - 4
	for x in a[4:]:
		xor = xor ^ x
	a.append(xor)
	
	# retrun in str type
	return "".join(map(chr, a)) # list を string に変換する (逆変換は map(ord, list('abcde')) )

# 終了処理
def DoTerminate():
	global bOnClose, ser, t1, t2
	bOnClose = True
	print("!TERMINATE")
	try :
		t1.cancel()
	except:
		pass

	time.sleep(0.5)
	ser.close()
	exit(0)

if __name__=='__main__':
	### now in main thread
	os.system('clear')
	print('Wait receive packets...')
	# parse command line arguments
	ParseArgs()
	
	# open serial port
	try:
		ser = OpenSerial(options.target, options.baud)
	except:
		exit(1)
		
	if ser == None: exit(1)
	if not ser.isOpen(): exit(1)

	# UART 入力
	t1=threading.Thread(target=WrkReadSerial)
	t1.setDaemon(True)
	t1.start()
	
	# 入出力が tty ならキーボード入力を有効とする
	bInteractive = stdin.isatty() # and stdout.isatty()
	
	try:
		while True:				
			# 標準入力から何か入力する (Enter 入力が必要)
			if bInteractive:
				l = stdin.readline()
				if l[0] == 'q':
					DoTerminate()
	except:
		if not bOnClose:
			DoTerminate()
