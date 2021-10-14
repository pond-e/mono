#!/usr/bin/env python
#encoding=utf-8

# 書式パーサーの基底クラス
class FmtBase:
    def __init__(self):
        self.reinit()

    def reinit(self):
        self.state = 'e'
        self.len = 0
        self.len_read = 0
        self.payload = []
        self.b_complete = False
        
    def s_other(self, c):
        self.state = 'e'

    def process(self, c): 
        self.key_dict.get(self.state, self.s_other)(c)

    def terminate(self):
        self.reinit()
    
    def is_comp(self):
        return self.b_complete
    
    def get_payload(self):
        return self.payload
    
    def get_payload_in_str(self):
        return "".join(map(chr, self.payload))

