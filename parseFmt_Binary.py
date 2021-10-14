#!/usr/bin/env python
#encoding=utf-8

from parseFmt import FmtBase

# バイナリ書式を解読する
class FmtBinary(FmtBase):
    def __init__(self):
        self.reinit()
        
        # 状態と呼び出すべき関数のテーブル
        self.key_dict = {
            'e' : self.s_empty,
            'h' : self.s_head,
            'L' : self.s_len1,
            'l' : self.s_len2,
            'p' : self.s_payload,
            'x' : self.s_xor,
        }

    def reinit(self):
        FmtBase.reinit(self)
        self.xor_read = 0
        self.xor_calc = 0
        
    def s_empty(self, c):
        if c == 0xA5:
            self.reinit()
            self.state = 'h'
            self.b_complete = False
        
    def s_head(self, c):
        if c == 0x5A: self.state = 'L'
        
    def s_len1(self, c):
        self.state = 'l'
    
    def s_len2(self, c):
        self.len = c
        self.state = 'p'
    
    def s_payload(self, c):
        self.len_read = self.len_read + 1
        self.payload.append(c)
        if self.len_read == self.len:
            self.state = 'x' 
        
    def s_xor(self, c):
        self.xor_read = c
        self.calc_xor()
        if self.xor_read == self.xor_calc:
            self.b_complete = True
        self.state = 'e'

    def calc_xor(self):
        self.xor_calc = 0
        for x in self.payload: 
            self.xor_calc ^= x
        return self.xor_calc
