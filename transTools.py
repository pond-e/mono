#!/usr/bin/env python
#encoding=utf-8

import os
from binascii import *
from struct import pack
from serial import *
from parseFmt_Binary import FmtBinary 

# serial port object
ser = None
Img = 0
Number = 1
End = 2


# シリアルポートのオープン
def OpenSerial(devname, baud=115200):
	global ser
	ser = Serial(devname, baud, timeout=0.5, parity=PARITY_NONE,
						stopbits=1, bytesize=8, rtscts=0, dsrdtr=0)
	return ser

# ACKが帰ってきたかどうかを判断する
def AckWait( cmax = 3 ):
	global ser
	count = 0
	ackfmt = FmtBinary()
	while True:
		ackpay = []
		try:
			ack = ord(ser.read(1))
		# when time out
		except TypeError:
			ackfmt.terminate()
			count += 1
			if count == cmax:
				ackpay = [0]*4
				break
			else:
				continue

		ackfmt.process(ack)
		if ackfmt.is_comp():
			ackpay = ackfmt.get_payload()
			ackfmt.terminate()

		if len(ackpay) == 4:
			break

	return ackpay[3]

# 進捗状況の表示
def ProgressBar( par, max_num ) :
	sample = 100.0/max_num
	prog = par/sample
	bar = ":"
	i = 0
	while i < prog :
		bar += "="
		i += 1
	bar += ">"
	while i < max_num :
		bar += "-"
		i += 1

	return bar

# ファイル名を決めるための数字を読み込み
def ReadFileNumber(filename):
	flag = os.path.exists(filename)
	if flag :
		f = open( filename, 'r' )
		line = f.readline()
		number = int(line.strip())
		f.close()
	else :
		number = 0

	return number

#	パケット生成関数
def GeneratePacket( address, ID, number ):
	if ID == Img:
		#	送信要求パケット
		p = pack( '>BBBBBB', address, 0xA0, 0x00, 0x01, 0xFF, 0x01  )			#	ACKを要求
	elif ID == Number:
	#	パケット数通知パケット
		p = pack( '>BBBBBH', address, 0xA0, 0x01, 0x01, 0xFF, number )
	elif ID == End:
	#	送信完了パケット
		p = pack( '>BBBBBBB3s', address, 0xA0, 0x03, 0x01, 0x02, 0x0F,  0xFF, 'end'  )

	# calc xor checksum
	xor = 0
	for i in range(0, len(p)):
		xor ^= ord(p[i])

	return pack(">HH%dsB" % len(p), 0xa55a, 0x8000 + len(p), p, xor)


#	送信パケットの全体数通知パケットの生成
def GenerateAllPacketNumber( address, number ):
	pkt = GeneratePacket( address, Number, number )
	ser.write(pkt)

#	終了パケットの生成
def GenerateEndRequest( address ):
	pkt = GeneratePacket( address, End, 0 )
	ser.write(pkt)

#	画像送信要求パケットの生成
def GenerateImageRequest( address ):
	global ser
	os.system('clear')
	print('Start Photograph Trancefer')
	pkt = GeneratePacket( address, Img, 0 )
	ser.write(pkt)

