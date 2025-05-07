import os
from typing import Any

import pyotp
import json
import requests
import execjs
import re
import base64

from PySide6.QtCore import Signal,QObject
from lxml import etree

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
class Worker(QObject):
    finished = Signal(Any)  # 任务完成信号
    started = Signal()  # 进度更新信号
    def __init__(self,run,run_on_finish=None,run_on_start=None):
        super().__init__()
        self.run = run
        self.run_on_finish = run_on_finish
        self.run_on_start = run_on_start
    def run_task(self):
        self.started.emit()
        if self.run_on_start is not None:
            self.run_on_start()

        ret = self.run()

        if self.run_on_finish is not None:
            self.run_on_finish()
        self.finished.emit(ret)
class encrypt:
    # base64解码js
    js = "d2luZG93PXt9O25hdmlnYXRvcj17fTt2YXIgZGJpdHMsIGNhbmFyeSA9IDB4ZGVhZGJlZWZjYWZlLCBqX2xtID0gMTU3MTUwNzAgPT0gKDE2Nzc3MjE1ICYgY2FuYXJ5KTsKZnVuY3Rpb24gQmlnSW50ZWdlcih0LCByLCBpKSB7CiAgICBudWxsICE9IHQgJiYgKCJudW1iZXIiID09IHR5cGVvZiB0ID8gdGhpcy5mcm9tTnVtYmVyKHQsIHIsIGkpIDogbnVsbCA9PSByICYmICJzdHJpbmciICE9IHR5cGVvZiB0ID8gdGhpcy5mcm9tU3RyaW5nKHQsIDI1NikgOiB0aGlzLmZyb21TdHJpbmcodCwgcikpCn0KZnVuY3Rpb24gbmJpKCkgewogICAgcmV0dXJuIG5ldyBCaWdJbnRlZ2VyKG51bGwpCn0KZnVuY3Rpb24gYW0xKHQsIHIsIGksIG4sIG8sIGUpIHsKICAgIGZvciAoOyAwIDw9IC0tZTsgKSB7CiAgICAgICAgdmFyIHMgPSByICogdGhpc1t0KytdICsgaVtuXSArIG87CiAgICAgICAgbyA9IE1hdGguZmxvb3IocyAvIDY3MTA4ODY0KSwKICAgICAgICBpW24rK10gPSA2NzEwODg2MyAmIHMKICAgIH0KICAgIHJldHVybiBvCn0KZnVuY3Rpb24gYW0yKHQsIHIsIGksIG4sIG8sIGUpIHsKICAgIGZvciAodmFyIHMgPSAzMjc2NyAmIHIsIGggPSByID4+IDE1OyAwIDw9IC0tZTsgKSB7CiAgICAgICAgdmFyIHAgPSAzMjc2NyAmIHRoaXNbdF0KICAgICAgICAgICwgZyA9IHRoaXNbdCsrXSA+PiAxNQogICAgICAgICAgLCB1ID0gaCAqIHAgKyBnICogczsKICAgICAgICBvID0gKChwID0gcyAqIHAgKyAoKDMyNzY3ICYgdSkgPDwgMTUpICsgaVtuXSArICgxMDczNzQxODIzICYgbykpID4+PiAzMCkgKyAodSA+Pj4gMTUpICsgaCAqIGcgKyAobyA+Pj4gMzApLAogICAgICAgIGlbbisrXSA9IDEwNzM3NDE4MjMgJiBwCiAgICB9CiAgICByZXR1cm4gbwp9CmZ1bmN0aW9uIGFtMyh0LCByLCBpLCBuLCBvLCBlKSB7CiAgICBmb3IgKHZhciBzID0gMTYzODMgJiByLCBoID0gciA+PiAxNDsgMCA8PSAtLWU7ICkgewogICAgICAgIHZhciBwID0gMTYzODMgJiB0aGlzW3RdCiAgICAgICAgICAsIGcgPSB0aGlzW3QrK10gPj4gMTQKICAgICAgICAgICwgdSA9IGggKiBwICsgZyAqIHM7CiAgICAgICAgbyA9ICgocCA9IHMgKiBwICsgKCgxNjM4MyAmIHUpIDw8IDE0KSArIGlbbl0gKyBvKSA+PiAyOCkgKyAodSA+PiAxNCkgKyBoICogZywKICAgICAgICBpW24rK10gPSAyNjg0MzU0NTUgJiBwCiAgICB9CiAgICByZXR1cm4gbwp9CmpfbG0gJiYgIk1pY3Jvc29mdCBJbnRlcm5ldCBFeHBsb3JlciIgPT0gbmF2aWdhdG9yLmFwcE5hbWUgPyAoQmlnSW50ZWdlci5wcm90b3R5cGUuYW0gPSBhbTIsCmRiaXRzID0gMzApIDogal9sbSAmJiAiTmV0c2NhcGUiICE9IG5hdmlnYXRvci5hcHBOYW1lID8gKEJpZ0ludGVnZXIucHJvdG90eXBlLmFtID0gYW0xLApkYml0cyA9IDI2KSA6IChCaWdJbnRlZ2VyLnByb3RvdHlwZS5hbSA9IGFtMywKZGJpdHMgPSAyOCksCkJpZ0ludGVnZXIucHJvdG90eXBlLkRCID0gZGJpdHMsCkJpZ0ludGVnZXIucHJvdG90eXBlLkRNID0gKDEgPDwgZGJpdHMpIC0gMSwKQmlnSW50ZWdlci5wcm90b3R5cGUuRFYgPSAxIDw8IGRiaXRzOwp2YXIgQklfRlAgPSA1MjsKQmlnSW50ZWdlci5wcm90b3R5cGUuRlYgPSBNYXRoLnBvdygyLCBCSV9GUCksCkJpZ0ludGVnZXIucHJvdG90eXBlLkYxID0gQklfRlAgLSBkYml0cywKQmlnSW50ZWdlci5wcm90b3R5cGUuRjIgPSAyICogZGJpdHMgLSBCSV9GUDsKdmFyIHJyLCB2diwgQklfUk0gPSAiMDEyMzQ1Njc4OWFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6IiwgQklfUkMgPSBuZXcgQXJyYXk7CmZvciAocnIgPSAiMCIuY2hhckNvZGVBdCgwKSwKdnYgPSAwOyB2diA8PSA5OyArK3Z2KQogICAgQklfUkNbcnIrK10gPSB2djsKZm9yIChyciA9ICJhIi5jaGFyQ29kZUF0KDApLAp2diA9IDEwOyB2diA8IDM2OyArK3Z2KQogICAgQklfUkNbcnIrK10gPSB2djsKZm9yIChyciA9ICJBIi5jaGFyQ29kZUF0KDApLAp2diA9IDEwOyB2diA8IDM2OyArK3Z2KQogICAgQklfUkNbcnIrK10gPSB2djsKZnVuY3Rpb24gaW50MmNoYXIodCkgewogICAgcmV0dXJuIEJJX1JNLmNoYXJBdCh0KQp9CmZ1bmN0aW9uIGludEF0KHQsIHIpIHsKICAgIHZhciBpID0gQklfUkNbdC5jaGFyQ29kZUF0KHIpXTsKICAgIHJldHVybiBudWxsID09IGkgPyAtMSA6IGkKfQpmdW5jdGlvbiBibnBDb3B5VG8odCkgewogICAgZm9yICh2YXIgciA9IHRoaXMudCAtIDE7IDAgPD0gcjsgLS1yKQogICAgICAgIHRbcl0gPSB0aGlzW3JdOwogICAgdC50ID0gdGhpcy50LAogICAgdC5zID0gdGhpcy5zCn0KZnVuY3Rpb24gYm5wRnJvbUludCh0KSB7CiAgICB0aGlzLnQgPSAxLAogICAgdGhpcy5zID0gdCA8IDAgPyAtMSA6IDAsCiAgICAwIDwgdCA/IHRoaXNbMF0gPSB0IDogdCA8IC0xID8gdGhpc1swXSA9IHQgKyB0aGlzLkRWIDogdGhpcy50ID0gMAp9CmZ1bmN0aW9uIG5idih0KSB7CiAgICB2YXIgciA9IG5iaSgpOwogICAgcmV0dXJuIHIuZnJvbUludCh0KSwKICAgIHIKfQpmdW5jdGlvbiBibnBGcm9tU3RyaW5nKHQsIHIpIHsKICAgIHZhciBpOwogICAgaWYgKDE2ID09IHIpCiAgICAgICAgaSA9IDQ7CiAgICBlbHNlIGlmICg4ID09IHIpCiAgICAgICAgaSA9IDM7CiAgICBlbHNlIGlmICgyNTYgPT0gcikKICAgICAgICBpID0gODsKICAgIGVsc2UgaWYgKDIgPT0gcikKICAgICAgICBpID0gMTsKICAgIGVsc2UgaWYgKDMyID09IHIpCiAgICAgICAgaSA9IDU7CiAgICBlbHNlIHsKICAgICAgICBpZiAoNCAhPSByKQogICAgICAgICAgICByZXR1cm4gdm9pZCB0aGlzLmZyb21SYWRpeCh0LCByKTsKICAgICAgICBpID0gMgogICAgfQogICAgdGhpcy50ID0gMCwKICAgIHRoaXMucyA9IDA7CiAgICBmb3IgKHZhciBuID0gdC5sZW5ndGgsIG8gPSAhMSwgZSA9IDA7IDAgPD0gLS1uOyApIHsKICAgICAgICB2YXIgcyA9IDggPT0gaSA/IDI1NSAmIHRbbl0gOiBpbnRBdCh0LCBuKTsKICAgICAgICBzIDwgMCA/ICItIiA9PSB0LmNoYXJBdChuKSAmJiAobyA9ICEwKSA6IChvID0gITEsCiAgICAgICAgMCA9PSBlID8gdGhpc1t0aGlzLnQrK10gPSBzIDogZSArIGkgPiB0aGlzLkRCID8gKHRoaXNbdGhpcy50IC0gMV0gfD0gKHMgJiAoMSA8PCB0aGlzLkRCIC0gZSkgLSAxKSA8PCBlLAogICAgICAgIHRoaXNbdGhpcy50KytdID0gcyA+PiB0aGlzLkRCIC0gZSkgOiB0aGlzW3RoaXMudCAtIDFdIHw9IHMgPDwgZSwKICAgICAgICAoZSArPSBpKSA+PSB0aGlzLkRCICYmIChlIC09IHRoaXMuREIpKQogICAgfQogICAgOCA9PSBpICYmIDAgIT0gKDEyOCAmIHRbMF0pICYmICh0aGlzLnMgPSAtMSwKICAgIDAgPCBlICYmICh0aGlzW3RoaXMudCAtIDFdIHw9ICgxIDw8IHRoaXMuREIgLSBlKSAtIDEgPDwgZSkpLAogICAgdGhpcy5jbGFtcCgpLAogICAgbyAmJiBCaWdJbnRlZ2VyLlpFUk8uc3ViVG8odGhpcywgdGhpcykKfQpmdW5jdGlvbiBibnBDbGFtcCgpIHsKICAgIGZvciAodmFyIHQgPSB0aGlzLnMgJiB0aGlzLkRNOyAwIDwgdGhpcy50ICYmIHRoaXNbdGhpcy50IC0gMV0gPT0gdDsgKQogICAgICAgIC0tdGhpcy50Cn0KZnVuY3Rpb24gYm5Ub1N0cmluZyh0KSB7CiAgICBpZiAodGhpcy5zIDwgMCkKICAgICAgICByZXR1cm4gIi0iICsgdGhpcy5uZWdhdGUoKS50b1N0cmluZyh0KTsKICAgIHZhciByOwogICAgaWYgKDE2ID09IHQpCiAgICAgICAgciA9IDQ7CiAgICBlbHNlIGlmICg4ID09IHQpCiAgICAgICAgciA9IDM7CiAgICBlbHNlIGlmICgyID09IHQpCiAgICAgICAgciA9IDE7CiAgICBlbHNlIGlmICgzMiA9PSB0KQogICAgICAgIHIgPSA1OwogICAgZWxzZSB7CiAgICAgICAgaWYgKDQgIT0gdCkKICAgICAgICAgICAgcmV0dXJuIHRoaXMudG9SYWRpeCh0KTsKICAgICAgICByID0gMgogICAgfQogICAgdmFyIGksIG4gPSAoMSA8PCByKSAtIDEsIG8gPSAhMSwgZSA9ICIiLCBzID0gdGhpcy50LCBoID0gdGhpcy5EQiAtIHMgKiB0aGlzLkRCICUgcjsKICAgIGlmICgwIDwgcy0tKQogICAgICAgIGZvciAoaCA8IHRoaXMuREIgJiYgMCA8IChpID0gdGhpc1tzXSA+PiBoKSAmJiAobyA9ICEwLAogICAgICAgIGUgPSBpbnQyY2hhcihpKSk7IDAgPD0gczsgKQogICAgICAgICAgICBoIDwgciA/IChpID0gKHRoaXNbc10gJiAoMSA8PCBoKSAtIDEpIDw8IHIgLSBoLAogICAgICAgICAgICBpIHw9IHRoaXNbLS1zXSA+PiAoaCArPSB0aGlzLkRCIC0gcikpIDogKGkgPSB0aGlzW3NdID4+IChoIC09IHIpICYgbiwKICAgICAgICAgICAgaCA8PSAwICYmIChoICs9IHRoaXMuREIsCiAgICAgICAgICAgIC0tcykpLAogICAgICAgICAgICAwIDwgaSAmJiAobyA9ICEwKSwKICAgICAgICAgICAgbyAmJiAoZSArPSBpbnQyY2hhcihpKSk7CiAgICByZXR1cm4gbyA/IGUgOiAiMCIKfQpmdW5jdGlvbiBibk5lZ2F0ZSgpIHsKICAgIHZhciB0ID0gbmJpKCk7CiAgICByZXR1cm4gQmlnSW50ZWdlci5aRVJPLnN1YlRvKHRoaXMsIHQpLAogICAgdAp9CmZ1bmN0aW9uIGJuQWJzKCkgewogICAgcmV0dXJuIHRoaXMucyA8IDAgPyB0aGlzLm5lZ2F0ZSgpIDogdGhpcwp9CmZ1bmN0aW9uIGJuQ29tcGFyZVRvKHQpIHsKICAgIHZhciByID0gdGhpcy5zIC0gdC5zOwogICAgaWYgKDAgIT0gcikKICAgICAgICByZXR1cm4gcjsKICAgIHZhciBpID0gdGhpcy50OwogICAgaWYgKDAgIT0gKHIgPSBpIC0gdC50KSkKICAgICAgICByZXR1cm4gdGhpcy5zIDwgMCA/IC1yIDogcjsKICAgIGZvciAoOyAwIDw9IC0taTsgKQogICAgICAgIGlmICgwICE9IChyID0gdGhpc1tpXSAtIHRbaV0pKQogICAgICAgICAgICByZXR1cm4gcjsKICAgIHJldHVybiAwCn0KZnVuY3Rpb24gbmJpdHModCkgewogICAgdmFyIHIsIGkgPSAxOwogICAgcmV0dXJuIDAgIT0gKHIgPSB0ID4+PiAxNikgJiYgKHQgPSByLAogICAgaSArPSAxNiksCiAgICAwICE9IChyID0gdCA+PiA4KSAmJiAodCA9IHIsCiAgICBpICs9IDgpLAogICAgMCAhPSAociA9IHQgPj4gNCkgJiYgKHQgPSByLAogICAgaSArPSA0KSwKICAgIDAgIT0gKHIgPSB0ID4+IDIpICYmICh0ID0gciwKICAgIGkgKz0gMiksCiAgICAwICE9IChyID0gdCA+PiAxKSAmJiAodCA9IHIsCiAgICBpICs9IDEpLAogICAgaQp9CmZ1bmN0aW9uIGJuQml0TGVuZ3RoKCkgewogICAgcmV0dXJuIHRoaXMudCA8PSAwID8gMCA6IHRoaXMuREIgKiAodGhpcy50IC0gMSkgKyBuYml0cyh0aGlzW3RoaXMudCAtIDFdIF4gdGhpcy5zICYgdGhpcy5ETSkKfQpmdW5jdGlvbiBibnBETFNoaWZ0VG8odCwgcikgewogICAgdmFyIGk7CiAgICBmb3IgKGkgPSB0aGlzLnQgLSAxOyAwIDw9IGk7IC0taSkKICAgICAgICByW2kgKyB0XSA9IHRoaXNbaV07CiAgICBmb3IgKGkgPSB0IC0gMTsgMCA8PSBpOyAtLWkpCiAgICAgICAgcltpXSA9IDA7CiAgICByLnQgPSB0aGlzLnQgKyB0LAogICAgci5zID0gdGhpcy5zCn0KZnVuY3Rpb24gYm5wRFJTaGlmdFRvKHQsIHIpIHsKICAgIGZvciAodmFyIGkgPSB0OyBpIDwgdGhpcy50OyArK2kpCiAgICAgICAgcltpIC0gdF0gPSB0aGlzW2ldOwogICAgci50ID0gTWF0aC5tYXgodGhpcy50IC0gdCwgMCksCiAgICByLnMgPSB0aGlzLnMKfQpmdW5jdGlvbiBibnBMU2hpZnRUbyh0LCByKSB7CiAgICB2YXIgaSwgbiA9IHQgJSB0aGlzLkRCLCBvID0gdGhpcy5EQiAtIG4sIGUgPSAoMSA8PCBvKSAtIDEsIHMgPSBNYXRoLmZsb29yKHQgLyB0aGlzLkRCKSwgaCA9IHRoaXMucyA8PCBuICYgdGhpcy5ETTsKICAgIGZvciAoaSA9IHRoaXMudCAtIDE7IDAgPD0gaTsgLS1pKQogICAgICAgIHJbaSArIHMgKyAxXSA9IHRoaXNbaV0gPj4gbyB8IGgsCiAgICAgICAgaCA9ICh0aGlzW2ldICYgZSkgPDwgbjsKICAgIGZvciAoaSA9IHMgLSAxOyAwIDw9IGk7IC0taSkKICAgICAgICByW2ldID0gMDsKICAgIHJbc10gPSBoLAogICAgci50ID0gdGhpcy50ICsgcyArIDEsCiAgICByLnMgPSB0aGlzLnMsCiAgICByLmNsYW1wKCkKfQpmdW5jdGlvbiBibnBSU2hpZnRUbyh0LCByKSB7CiAgICByLnMgPSB0aGlzLnM7CiAgICB2YXIgaSA9IE1hdGguZmxvb3IodCAvIHRoaXMuREIpOwogICAgaWYgKGkgPj0gdGhpcy50KQogICAgICAgIHIudCA9IDA7CiAgICBlbHNlIHsKICAgICAgICB2YXIgbiA9IHQgJSB0aGlzLkRCCiAgICAgICAgICAsIG8gPSB0aGlzLkRCIC0gbgogICAgICAgICAgLCBlID0gKDEgPDwgbikgLSAxOwogICAgICAgIHJbMF0gPSB0aGlzW2ldID4+IG47CiAgICAgICAgZm9yICh2YXIgcyA9IGkgKyAxOyBzIDwgdGhpcy50OyArK3MpCiAgICAgICAgICAgIHJbcyAtIGkgLSAxXSB8PSAodGhpc1tzXSAmIGUpIDw8IG8sCiAgICAgICAgICAgIHJbcyAtIGldID0gdGhpc1tzXSA+PiBuOwogICAgICAgIDAgPCBuICYmIChyW3RoaXMudCAtIGkgLSAxXSB8PSAodGhpcy5zICYgZSkgPDwgbyksCiAgICAgICAgci50ID0gdGhpcy50IC0gaSwKICAgICAgICByLmNsYW1wKCkKICAgIH0KfQpmdW5jdGlvbiBibnBTdWJUbyh0LCByKSB7CiAgICBmb3IgKHZhciBpID0gMCwgbiA9IDAsIG8gPSBNYXRoLm1pbih0LnQsIHRoaXMudCk7IGkgPCBvOyApCiAgICAgICAgbiArPSB0aGlzW2ldIC0gdFtpXSwKICAgICAgICByW2krK10gPSBuICYgdGhpcy5ETSwKICAgICAgICBuID4+PSB0aGlzLkRCOwogICAgaWYgKHQudCA8IHRoaXMudCkgewogICAgICAgIGZvciAobiAtPSB0LnM7IGkgPCB0aGlzLnQ7ICkKICAgICAgICAgICAgbiArPSB0aGlzW2ldLAogICAgICAgICAgICByW2krK10gPSBuICYgdGhpcy5ETSwKICAgICAgICAgICAgbiA+Pj0gdGhpcy5EQjsKICAgICAgICBuICs9IHRoaXMucwogICAgfSBlbHNlIHsKICAgICAgICBmb3IgKG4gKz0gdGhpcy5zOyBpIDwgdC50OyApCiAgICAgICAgICAgIG4gLT0gdFtpXSwKICAgICAgICAgICAgcltpKytdID0gbiAmIHRoaXMuRE0sCiAgICAgICAgICAgIG4gPj49IHRoaXMuREI7CiAgICAgICAgbiAtPSB0LnMKICAgIH0KICAgIHIucyA9IG4gPCAwID8gLTEgOiAwLAogICAgbiA8IC0xID8gcltpKytdID0gdGhpcy5EViArIG4gOiAwIDwgbiAmJiAocltpKytdID0gbiksCiAgICByLnQgPSBpLAogICAgci5jbGFtcCgpCn0KZnVuY3Rpb24gYm5wTXVsdGlwbHlUbyh0LCByKSB7CiAgICB2YXIgaSA9IHRoaXMuYWJzKCkKICAgICAgLCBuID0gdC5hYnMoKQogICAgICAsIG8gPSBpLnQ7CiAgICBmb3IgKHIudCA9IG8gKyBuLnQ7IDAgPD0gLS1vOyApCiAgICAgICAgcltvXSA9IDA7CiAgICBmb3IgKG8gPSAwOyBvIDwgbi50OyArK28pCiAgICAgICAgcltvICsgaS50XSA9IGkuYW0oMCwgbltvXSwgciwgbywgMCwgaS50KTsKICAgIHIucyA9IDAsCiAgICByLmNsYW1wKCksCiAgICB0aGlzLnMgIT0gdC5zICYmIEJpZ0ludGVnZXIuWkVSTy5zdWJUbyhyLCByKQp9CmZ1bmN0aW9uIGJucFNxdWFyZVRvKHQpIHsKICAgIGZvciAodmFyIHIgPSB0aGlzLmFicygpLCBpID0gdC50ID0gMiAqIHIudDsgMCA8PSAtLWk7ICkKICAgICAgICB0W2ldID0gMDsKICAgIGZvciAoaSA9IDA7IGkgPCByLnQgLSAxOyArK2kpIHsKICAgICAgICB2YXIgbiA9IHIuYW0oaSwgcltpXSwgdCwgMiAqIGksIDAsIDEpOwogICAgICAgICh0W2kgKyByLnRdICs9IHIuYW0oaSArIDEsIDIgKiByW2ldLCB0LCAyICogaSArIDEsIG4sIHIudCAtIGkgLSAxKSkgPj0gci5EViAmJiAodFtpICsgci50XSAtPSByLkRWLAogICAgICAgIHRbaSArIHIudCArIDFdID0gMSkKICAgIH0KICAgIDAgPCB0LnQgJiYgKHRbdC50IC0gMV0gKz0gci5hbShpLCByW2ldLCB0LCAyICogaSwgMCwgMSkpLAogICAgdC5zID0gMCwKICAgIHQuY2xhbXAoKQp9CmZ1bmN0aW9uIGJucERpdlJlbVRvKHQsIHIsIGkpIHsKICAgIHZhciBuID0gdC5hYnMoKTsKICAgIGlmICghKG4udCA8PSAwKSkgewogICAgICAgIHZhciBvID0gdGhpcy5hYnMoKTsKICAgICAgICBpZiAoby50IDwgbi50KQogICAgICAgICAgICByZXR1cm4gbnVsbCAhPSByICYmIHIuZnJvbUludCgwKSwKICAgICAgICAgICAgdm9pZCAobnVsbCAhPSBpICYmIHRoaXMuY29weVRvKGkpKTsKICAgICAgICBudWxsID09IGkgJiYgKGkgPSBuYmkoKSk7CiAgICAgICAgdmFyIGUgPSBuYmkoKQogICAgICAgICAgLCBzID0gdGhpcy5zCiAgICAgICAgICAsIGggPSB0LnMKICAgICAgICAgICwgcCA9IHRoaXMuREIgLSBuYml0cyhuW24udCAtIDFdKTsKICAgICAgICAwIDwgcCA/IChuLmxTaGlmdFRvKHAsIGUpLAogICAgICAgIG8ubFNoaWZ0VG8ocCwgaSkpIDogKG4uY29weVRvKGUpLAogICAgICAgIG8uY29weVRvKGkpKTsKICAgICAgICB2YXIgZyA9IGUudAogICAgICAgICAgLCB1ID0gZVtnIC0gMV07CiAgICAgICAgaWYgKDAgIT0gdSkgewogICAgICAgICAgICB2YXIgYSA9IHUgKiAoMSA8PCB0aGlzLkYxKSArICgxIDwgZyA/IGVbZyAtIDJdID4+IHRoaXMuRjIgOiAwKQogICAgICAgICAgICAgICwgZiA9IHRoaXMuRlYgLyBhCiAgICAgICAgICAgICAgLCBsID0gKDEgPDwgdGhpcy5GMSkgLyBhCiAgICAgICAgICAgICAgLCBjID0gMSA8PCB0aGlzLkYyCiAgICAgICAgICAgICAgLCBtID0gaS50CiAgICAgICAgICAgICAgLCB2ID0gbSAtIGcKICAgICAgICAgICAgICAsIGIgPSBudWxsID09IHIgPyBuYmkoKSA6IHI7CiAgICAgICAgICAgIGZvciAoZS5kbFNoaWZ0VG8odiwgYiksCiAgICAgICAgICAgIDAgPD0gaS5jb21wYXJlVG8oYikgJiYgKGlbaS50KytdID0gMSwKICAgICAgICAgICAgaS5zdWJUbyhiLCBpKSksCiAgICAgICAgICAgIEJpZ0ludGVnZXIuT05FLmRsU2hpZnRUbyhnLCBiKSwKICAgICAgICAgICAgYi5zdWJUbyhlLCBlKTsgZS50IDwgZzsgKQogICAgICAgICAgICAgICAgZVtlLnQrK10gPSAwOwogICAgICAgICAgICBmb3IgKDsgMCA8PSAtLXY7ICkgewogICAgICAgICAgICAgICAgdmFyIHkgPSBpWy0tbV0gPT0gdSA/IHRoaXMuRE0gOiBNYXRoLmZsb29yKGlbbV0gKiBmICsgKGlbbSAtIDFdICsgYykgKiBsKTsKICAgICAgICAgICAgICAgIGlmICgoaVttXSArPSBlLmFtKDAsIHksIGksIHYsIDAsIGcpKSA8IHkpCiAgICAgICAgICAgICAgICAgICAgZm9yIChlLmRsU2hpZnRUbyh2LCBiKSwKICAgICAgICAgICAgICAgICAgICBpLnN1YlRvKGIsIGkpOyBpW21dIDwgLS15OyApCiAgICAgICAgICAgICAgICAgICAgICAgIGkuc3ViVG8oYiwgaSkKICAgICAgICAgICAgfQogICAgICAgICAgICBudWxsICE9IHIgJiYgKGkuZHJTaGlmdFRvKGcsIHIpLAogICAgICAgICAgICBzICE9IGggJiYgQmlnSW50ZWdlci5aRVJPLnN1YlRvKHIsIHIpKSwKICAgICAgICAgICAgaS50ID0gZywKICAgICAgICAgICAgaS5jbGFtcCgpLAogICAgICAgICAgICAwIDwgcCAmJiBpLnJTaGlmdFRvKHAsIGkpLAogICAgICAgICAgICBzIDwgMCAmJiBCaWdJbnRlZ2VyLlpFUk8uc3ViVG8oaSwgaSkKICAgICAgICB9CiAgICB9Cn0KZnVuY3Rpb24gYm5Nb2QodCkgewogICAgdmFyIHIgPSBuYmkoKTsKICAgIHJldHVybiB0aGlzLmFicygpLmRpdlJlbVRvKHQsIG51bGwsIHIpLAogICAgdGhpcy5zIDwgMCAmJiAwIDwgci5jb21wYXJlVG8oQmlnSW50ZWdlci5aRVJPKSAmJiB0LnN1YlRvKHIsIHIpLAogICAgcgp9CmZ1bmN0aW9uIENsYXNzaWModCkgewogICAgdGhpcy5tID0gdAp9CmZ1bmN0aW9uIGNDb252ZXJ0KHQpIHsKICAgIHJldHVybiB0LnMgPCAwIHx8IDAgPD0gdC5jb21wYXJlVG8odGhpcy5tKSA/IHQubW9kKHRoaXMubSkgOiB0Cn0KZnVuY3Rpb24gY1JldmVydCh0KSB7CiAgICByZXR1cm4gdAp9CmZ1bmN0aW9uIGNSZWR1Y2UodCkgewogICAgdC5kaXZSZW1Ubyh0aGlzLm0sIG51bGwsIHQpCn0KZnVuY3Rpb24gY011bFRvKHQsIHIsIGkpIHsKICAgIHQubXVsdGlwbHlUbyhyLCBpKSwKICAgIHRoaXMucmVkdWNlKGkpCn0KZnVuY3Rpb24gY1NxclRvKHQsIHIpIHsKICAgIHQuc3F1YXJlVG8ociksCiAgICB0aGlzLnJlZHVjZShyKQp9CmZ1bmN0aW9uIGJucEludkRpZ2l0KCkgewogICAgaWYgKHRoaXMudCA8IDEpCiAgICAgICAgcmV0dXJuIDA7CiAgICB2YXIgdCA9IHRoaXNbMF07CiAgICBpZiAoMCA9PSAoMSAmIHQpKQogICAgICAgIHJldHVybiAwOwogICAgdmFyIHIgPSAzICYgdDsKICAgIHJldHVybiAwIDwgKHIgPSAociA9IChyID0gKHIgPSByICogKDIgLSAoMTUgJiB0KSAqIHIpICYgMTUpICogKDIgLSAoMjU1ICYgdCkgKiByKSAmIDI1NSkgKiAoMiAtICgoNjU1MzUgJiB0KSAqIHIgJiA2NTUzNSkpICYgNjU1MzUpICogKDIgLSB0ICogciAlIHRoaXMuRFYpICUgdGhpcy5EVikgPyB0aGlzLkRWIC0gciA6IC1yCn0KZnVuY3Rpb24gTW9udGdvbWVyeSh0KSB7CiAgICB0aGlzLm0gPSB0LAogICAgdGhpcy5tcCA9IHQuaW52RGlnaXQoKSwKICAgIHRoaXMubXBsID0gMzI3NjcgJiB0aGlzLm1wLAogICAgdGhpcy5tcGggPSB0aGlzLm1wID4+IDE1LAogICAgdGhpcy51bSA9ICgxIDw8IHQuREIgLSAxNSkgLSAxLAogICAgdGhpcy5tdDIgPSAyICogdC50Cn0KZnVuY3Rpb24gbW9udENvbnZlcnQodCkgewogICAgdmFyIHIgPSBuYmkoKTsKICAgIHJldHVybiB0LmFicygpLmRsU2hpZnRUbyh0aGlzLm0udCwgciksCiAgICByLmRpdlJlbVRvKHRoaXMubSwgbnVsbCwgciksCiAgICB0LnMgPCAwICYmIDAgPCByLmNvbXBhcmVUbyhCaWdJbnRlZ2VyLlpFUk8pICYmIHRoaXMubS5zdWJUbyhyLCByKSwKICAgIHIKfQpmdW5jdGlvbiBtb250UmV2ZXJ0KHQpIHsKICAgIHZhciByID0gbmJpKCk7CiAgICByZXR1cm4gdC5jb3B5VG8ociksCiAgICB0aGlzLnJlZHVjZShyKSwKICAgIHIKfQpmdW5jdGlvbiBtb250UmVkdWNlKHQpIHsKICAgIGZvciAoOyB0LnQgPD0gdGhpcy5tdDI7ICkKICAgICAgICB0W3QudCsrXSA9IDA7CiAgICBmb3IgKHZhciByID0gMDsgciA8IHRoaXMubS50OyArK3IpIHsKICAgICAgICB2YXIgaSA9IDMyNzY3ICYgdFtyXQogICAgICAgICAgLCBuID0gaSAqIHRoaXMubXBsICsgKChpICogdGhpcy5tcGggKyAodFtyXSA+PiAxNSkgKiB0aGlzLm1wbCAmIHRoaXMudW0pIDw8IDE1KSAmIHQuRE07CiAgICAgICAgZm9yICh0W2kgPSByICsgdGhpcy5tLnRdICs9IHRoaXMubS5hbSgwLCBuLCB0LCByLCAwLCB0aGlzLm0udCk7IHRbaV0gPj0gdC5EVjsgKQogICAgICAgICAgICB0W2ldIC09IHQuRFYsCiAgICAgICAgICAgIHRbKytpXSsrCiAgICB9CiAgICB0LmNsYW1wKCksCiAgICB0LmRyU2hpZnRUbyh0aGlzLm0udCwgdCksCiAgICAwIDw9IHQuY29tcGFyZVRvKHRoaXMubSkgJiYgdC5zdWJUbyh0aGlzLm0sIHQpCn0KZnVuY3Rpb24gbW9udFNxclRvKHQsIHIpIHsKICAgIHQuc3F1YXJlVG8ociksCiAgICB0aGlzLnJlZHVjZShyKQp9CmZ1bmN0aW9uIG1vbnRNdWxUbyh0LCByLCBpKSB7CiAgICB0Lm11bHRpcGx5VG8ociwgaSksCiAgICB0aGlzLnJlZHVjZShpKQp9CmZ1bmN0aW9uIGJucElzRXZlbigpIHsKICAgIHJldHVybiAwID09ICgwIDwgdGhpcy50ID8gMSAmIHRoaXNbMF0gOiB0aGlzLnMpCn0KZnVuY3Rpb24gYm5wRXhwKHQsIHIpIHsKICAgIGlmICg0Mjk0OTY3Mjk1IDwgdCB8fCB0IDwgMSkKICAgICAgICByZXR1cm4gQmlnSW50ZWdlci5PTkU7CiAgICB2YXIgaSA9IG5iaSgpCiAgICAgICwgbiA9IG5iaSgpCiAgICAgICwgbyA9IHIuY29udmVydCh0aGlzKQogICAgICAsIGUgPSBuYml0cyh0KSAtIDE7CiAgICBmb3IgKG8uY29weVRvKGkpOyAwIDw9IC0tZTsgKQogICAgICAgIGlmIChyLnNxclRvKGksIG4pLAogICAgICAgIDAgPCAodCAmIDEgPDwgZSkpCiAgICAgICAgICAgIHIubXVsVG8obiwgbywgaSk7CiAgICAgICAgZWxzZSB7CiAgICAgICAgICAgIHZhciBzID0gaTsKICAgICAgICAgICAgaSA9IG4sCiAgICAgICAgICAgIG4gPSBzCiAgICAgICAgfQogICAgcmV0dXJuIHIucmV2ZXJ0KGkpCn0KZnVuY3Rpb24gYm5Nb2RQb3dJbnQodCwgcikgewogICAgdmFyIGk7CiAgICByZXR1cm4gaSA9IHQgPCAyNTYgfHwgci5pc0V2ZW4oKSA/IG5ldyBDbGFzc2ljKHIpIDogbmV3IE1vbnRnb21lcnkociksCiAgICB0aGlzLmV4cCh0LCBpKQp9CmZ1bmN0aW9uIEFyY2ZvdXIoKSB7CiAgICB0aGlzLmkgPSAwLAogICAgdGhpcy5qID0gMCwKICAgIHRoaXMuUyA9IG5ldyBBcnJheQp9CmZ1bmN0aW9uIEFSQzRpbml0KHQpIHsKICAgIHZhciByLCBpLCBuOwogICAgZm9yIChyID0gMDsgciA8IDI1NjsgKytyKQogICAgICAgIHRoaXMuU1tyXSA9IHI7CiAgICBmb3IgKHIgPSBpID0gMDsgciA8IDI1NjsgKytyKQogICAgICAgIGkgPSBpICsgdGhpcy5TW3JdICsgdFtyICUgdC5sZW5ndGhdICYgMjU1LAogICAgICAgIG4gPSB0aGlzLlNbcl0sCiAgICAgICAgdGhpcy5TW3JdID0gdGhpcy5TW2ldLAogICAgICAgIHRoaXMuU1tpXSA9IG47CiAgICB0aGlzLmkgPSAwLAogICAgdGhpcy5qID0gMAp9CmZ1bmN0aW9uIEFSQzRuZXh0KCkgewogICAgdmFyIHQ7CiAgICByZXR1cm4gdGhpcy5pID0gdGhpcy5pICsgMSAmIDI1NSwKICAgIHRoaXMuaiA9IHRoaXMuaiArIHRoaXMuU1t0aGlzLmldICYgMjU1LAogICAgdCA9IHRoaXMuU1t0aGlzLmldLAogICAgdGhpcy5TW3RoaXMuaV0gPSB0aGlzLlNbdGhpcy5qXSwKICAgIHRoaXMuU1t0aGlzLmpdID0gdCwKICAgIHRoaXMuU1t0ICsgdGhpcy5TW3RoaXMuaV0gJiAyNTVdCn0KZnVuY3Rpb24gcHJuZ19uZXdzdGF0ZSgpIHsKICAgIHJldHVybiBuZXcgQXJjZm91cgp9CkNsYXNzaWMucHJvdG90eXBlLmNvbnZlcnQgPSBjQ29udmVydCwKQ2xhc3NpYy5wcm90b3R5cGUucmV2ZXJ0ID0gY1JldmVydCwKQ2xhc3NpYy5wcm90b3R5cGUucmVkdWNlID0gY1JlZHVjZSwKQ2xhc3NpYy5wcm90b3R5cGUubXVsVG8gPSBjTXVsVG8sCkNsYXNzaWMucHJvdG90eXBlLnNxclRvID0gY1NxclRvLApNb250Z29tZXJ5LnByb3RvdHlwZS5jb252ZXJ0ID0gbW9udENvbnZlcnQsCk1vbnRnb21lcnkucHJvdG90eXBlLnJldmVydCA9IG1vbnRSZXZlcnQsCk1vbnRnb21lcnkucHJvdG90eXBlLnJlZHVjZSA9IG1vbnRSZWR1Y2UsCk1vbnRnb21lcnkucHJvdG90eXBlLm11bFRvID0gbW9udE11bFRvLApNb250Z29tZXJ5LnByb3RvdHlwZS5zcXJUbyA9IG1vbnRTcXJUbywKQmlnSW50ZWdlci5wcm90b3R5cGUuY29weVRvID0gYm5wQ29weVRvLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5mcm9tSW50ID0gYm5wRnJvbUludCwKQmlnSW50ZWdlci5wcm90b3R5cGUuZnJvbVN0cmluZyA9IGJucEZyb21TdHJpbmcsCkJpZ0ludGVnZXIucHJvdG90eXBlLmNsYW1wID0gYm5wQ2xhbXAsCkJpZ0ludGVnZXIucHJvdG90eXBlLmRsU2hpZnRUbyA9IGJucERMU2hpZnRUbywKQmlnSW50ZWdlci5wcm90b3R5cGUuZHJTaGlmdFRvID0gYm5wRFJTaGlmdFRvLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5sU2hpZnRUbyA9IGJucExTaGlmdFRvLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5yU2hpZnRUbyA9IGJucFJTaGlmdFRvLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5zdWJUbyA9IGJucFN1YlRvLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5tdWx0aXBseVRvID0gYm5wTXVsdGlwbHlUbywKQmlnSW50ZWdlci5wcm90b3R5cGUuc3F1YXJlVG8gPSBibnBTcXVhcmVUbywKQmlnSW50ZWdlci5wcm90b3R5cGUuZGl2UmVtVG8gPSBibnBEaXZSZW1UbywKQmlnSW50ZWdlci5wcm90b3R5cGUuaW52RGlnaXQgPSBibnBJbnZEaWdpdCwKQmlnSW50ZWdlci5wcm90b3R5cGUuaXNFdmVuID0gYm5wSXNFdmVuLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5leHAgPSBibnBFeHAsCkJpZ0ludGVnZXIucHJvdG90eXBlLnRvU3RyaW5nID0gYm5Ub1N0cmluZywKQmlnSW50ZWdlci5wcm90b3R5cGUubmVnYXRlID0gYm5OZWdhdGUsCkJpZ0ludGVnZXIucHJvdG90eXBlLmFicyA9IGJuQWJzLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5jb21wYXJlVG8gPSBibkNvbXBhcmVUbywKQmlnSW50ZWdlci5wcm90b3R5cGUuYml0TGVuZ3RoID0gYm5CaXRMZW5ndGgsCkJpZ0ludGVnZXIucHJvdG90eXBlLm1vZCA9IGJuTW9kLApCaWdJbnRlZ2VyLnByb3RvdHlwZS5tb2RQb3dJbnQgPSBibk1vZFBvd0ludCwKQmlnSW50ZWdlci5aRVJPID0gbmJ2KDApLApCaWdJbnRlZ2VyLk9ORSA9IG5idigxKSwKQXJjZm91ci5wcm90b3R5cGUuaW5pdCA9IEFSQzRpbml0LApBcmNmb3VyLnByb3RvdHlwZS5uZXh0ID0gQVJDNG5leHQ7CnZhciBybmdfc3RhdGUsIHJuZ19wb29sLCBybmdfcHB0ciwgcm5nX3BzaXplID0gMjU2OwpmdW5jdGlvbiBybmdfc2VlZF9pbnQodCkgewogICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gXj0gMjU1ICYgdCwKICAgIHJuZ19wb29sW3JuZ19wcHRyKytdIF49IHQgPj4gOCAmIDI1NSwKICAgIHJuZ19wb29sW3JuZ19wcHRyKytdIF49IHQgPj4gMTYgJiAyNTUsCiAgICBybmdfcG9vbFtybmdfcHB0cisrXSBePSB0ID4+IDI0ICYgMjU1LAogICAgcm5nX3BzaXplIDw9IHJuZ19wcHRyICYmIChybmdfcHB0ciAtPSBybmdfcHNpemUpCn0KZnVuY3Rpb24gcm5nX3NlZWRfdGltZSgpIHsKICAgIHJuZ19zZWVkX2ludCgobmV3IERhdGUpLmdldFRpbWUoKSkKfQppZiAobnVsbCA9PSBybmdfcG9vbCkgewogICAgdmFyIHQ7CiAgICBpZiAocm5nX3Bvb2wgPSBuZXcgQXJyYXksCiAgICBybmdfcHB0ciA9IDAsCiAgICB3aW5kb3cuY3J5cHRvICYmIHdpbmRvdy5jcnlwdG8uZ2V0UmFuZG9tVmFsdWVzKSB7CiAgICAgICAgdmFyIHVhID0gbmV3IFVpbnQ4QXJyYXkoMzIpOwogICAgICAgIGZvciAod2luZG93LmNyeXB0by5nZXRSYW5kb21WYWx1ZXModWEpLAogICAgICAgIHQgPSAwOyB0IDwgMzI7ICsrdCkKICAgICAgICAgICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gPSB1YVt0XQogICAgfQogICAgaWYgKCJOZXRzY2FwZSIgPT0gbmF2aWdhdG9yLmFwcE5hbWUgJiYgbmF2aWdhdG9yLmFwcFZlcnNpb24gPCAiNSIgJiYgd2luZG93LmNyeXB0bykgewogICAgICAgIHZhciB6ID0gd2luZG93LmNyeXB0by5yYW5kb20oMzIpOwogICAgICAgIGZvciAodCA9IDA7IHQgPCB6Lmxlbmd0aDsgKyt0KQogICAgICAgICAgICBybmdfcG9vbFtybmdfcHB0cisrXSA9IDI1NSAmIHouY2hhckNvZGVBdCh0KQogICAgfQogICAgZm9yICg7IHJuZ19wcHRyIDwgcm5nX3BzaXplOyApCiAgICAgICAgdCA9IE1hdGguZmxvb3IoNjU1MzYgKiBNYXRoLnJhbmRvbSgpKSwKICAgICAgICBybmdfcG9vbFtybmdfcHB0cisrXSA9IHQgPj4+IDgsCiAgICAgICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gPSAyNTUgJiB0OwogICAgcm5nX3BwdHIgPSAwLAogICAgcm5nX3NlZWRfdGltZSgpCn0KZnVuY3Rpb24gcm5nX2dldF9ieXRlKCkgewogICAgaWYgKG51bGwgPT0gcm5nX3N0YXRlKSB7CiAgICAgICAgZm9yIChybmdfc2VlZF90aW1lKCksCiAgICAgICAgKHJuZ19zdGF0ZSA9IHBybmdfbmV3c3RhdGUoKSkuaW5pdChybmdfcG9vbCksCiAgICAgICAgcm5nX3BwdHIgPSAwOyBybmdfcHB0ciA8IHJuZ19wb29sLmxlbmd0aDsgKytybmdfcHB0cikKICAgICAgICAgICAgcm5nX3Bvb2xbcm5nX3BwdHJdID0gMDsKICAgICAgICBybmdfcHB0ciA9IDAKICAgIH0KICAgIHJldHVybiBybmdfc3RhdGUubmV4dCgpCn0KZnVuY3Rpb24gcm5nX2dldF9ieXRlcyh0KSB7CiAgICB2YXIgcjsKICAgIGZvciAociA9IDA7IHIgPCB0Lmxlbmd0aDsgKytyKQogICAgICAgIHRbcl0gPSBybmdfZ2V0X2J5dGUoKQp9CmZ1bmN0aW9uIFNlY3VyZVJhbmRvbSgpIHt9CmZ1bmN0aW9uIHBhcnNlQmlnSW50KHQsIHIpIHsKICAgIHJldHVybiBuZXcgQmlnSW50ZWdlcih0LHIpCn0KZnVuY3Rpb24gbGluZWJyayh0LCByKSB7CiAgICBmb3IgKHZhciBpID0gIiIsIG4gPSAwOyBuICsgciA8IHQubGVuZ3RoOyApCiAgICAgICAgaSArPSB0LnN1YnN0cmluZyhuLCBuICsgcikgKyAiXG4iLAogICAgICAgIG4gKz0gcjsKICAgIHJldHVybiBpICsgdC5zdWJzdHJpbmcobiwgdC5sZW5ndGgpCn0KZnVuY3Rpb24gYnl0ZTJIZXgodCkgewogICAgcmV0dXJuIHQgPCAxNiA/ICIwIiArIHQudG9TdHJpbmcoMTYpIDogdC50b1N0cmluZygxNikKfQpmdW5jdGlvbiBwa2NzMXBhZDIodCwgcikgewogICAgaWYgKHIgPCB0Lmxlbmd0aCArIDExKQogICAgICAgIHJldHVybiBjb25zb2xlICYmIGNvbnNvbGUuZXJyb3IgJiYgY29uc29sZS5lcnJvcigiTWVzc2FnZSB0b28gbG9uZyBmb3IgUlNBIiksCiAgICAgICAgbnVsbDsKICAgIGZvciAodmFyIGkgPSBuZXcgQXJyYXksIG4gPSB0Lmxlbmd0aCAtIDE7IDAgPD0gbiAmJiAwIDwgcjsgKSB7CiAgICAgICAgdmFyIG8gPSB0LmNoYXJDb2RlQXQobi0tKTsKICAgICAgICBvIDwgMTI4ID8gaVstLXJdID0gbyA6IDEyNyA8IG8gJiYgbyA8IDIwNDggPyAoaVstLXJdID0gNjMgJiBvIHwgMTI4LAogICAgICAgIGlbLS1yXSA9IG8gPj4gNiB8IDE5MikgOiAoaVstLXJdID0gNjMgJiBvIHwgMTI4LAogICAgICAgIGlbLS1yXSA9IG8gPj4gNiAmIDYzIHwgMTI4LAogICAgICAgIGlbLS1yXSA9IG8gPj4gMTIgfCAyMjQpCiAgICB9CiAgICBpWy0tcl0gPSAwOwogICAgZm9yICh2YXIgZSA9IG5ldyBTZWN1cmVSYW5kb20sIHMgPSBuZXcgQXJyYXk7IDIgPCByOyApIHsKICAgICAgICBmb3IgKHNbMF0gPSAwOyAwID09IHNbMF07ICkKICAgICAgICAgICAgZS5uZXh0Qnl0ZXMocyk7CiAgICAgICAgaVstLXJdID0gc1swXQogICAgfQogICAgcmV0dXJuIGlbLS1yXSA9IDIsCiAgICBpWy0tcl0gPSAwLAogICAgbmV3IEJpZ0ludGVnZXIoaSkKfQpmdW5jdGlvbiBSU0FLZXkoKSB7CiAgICB0aGlzLm4gPSBudWxsLAogICAgdGhpcy5lID0gMCwKICAgIHRoaXMuZCA9IG51bGwsCiAgICB0aGlzLnAgPSBudWxsLAogICAgdGhpcy5xID0gbnVsbCwKICAgIHRoaXMuZG1wMSA9IG51bGwsCiAgICB0aGlzLmRtcTEgPSBudWxsLAogICAgdGhpcy5jb2VmZiA9IG51bGwKfQpmdW5jdGlvbiBSU0FTZXRQdWJsaWModCwgcikgewogICAgbnVsbCAhPSB0ICYmIG51bGwgIT0gciAmJiAwIDwgdC5sZW5ndGggJiYgMCA8IHIubGVuZ3RoID8gKHRoaXMubiA9IHBhcnNlQmlnSW50KHQsIDE2KSwKICAgIHRoaXMuZSA9IHBhcnNlSW50KHIsIDE2KSkgOiBhbGVydCgiSW52YWxpZCBSU0EgcHVibGljIGtleSIpCn0KZnVuY3Rpb24gUlNBRG9QdWJsaWModCkgewogICAgcmV0dXJuIHQubW9kUG93SW50KHRoaXMuZSwgdGhpcy5uKQp9CmZ1bmN0aW9uIFJTQUVuY3J5cHQodCkgewogICAgdmFyIHIgPSBwa2NzMXBhZDIodCwgdGhpcy5uLmJpdExlbmd0aCgpICsgNyA+PiAzKTsKICAgIGlmIChudWxsID09IHIpCiAgICAgICAgcmV0dXJuIG51bGw7CiAgICB2YXIgaSA9IHRoaXMuZG9QdWJsaWMocik7CiAgICByZXR1cm4gbnVsbCA9PSBpID8gbnVsbCA6IEZpeEVuY3J5cHRMZW5ndGgoaS50b1N0cmluZygxNikpCn0KZnVuY3Rpb24gRml4RW5jcnlwdExlbmd0aCh0KSB7CiAgICB2YXIgciwgaSwgbiwgbyA9IHQubGVuZ3RoLCBlID0gWzEyOCwgMjU2LCA1MTIsIDEwMjQsIDIwNDgsIDQwOTZdOwogICAgZm9yIChpID0gMDsgaSA8IGUubGVuZ3RoOyBpKyspIHsKICAgICAgICBpZiAobyA9PT0gKHIgPSBlW2ldKSkKICAgICAgICAgICAgcmV0dXJuIHQ7CiAgICAgICAgaWYgKG8gPCByKSB7CiAgICAgICAgICAgIHZhciBzID0gciAtIG8KICAgICAgICAgICAgICAsIGggPSAiIjsKICAgICAgICAgICAgZm9yIChuID0gMDsgbiA8IHM7IG4rKykKICAgICAgICAgICAgICAgIGggKz0gIjAiOwogICAgICAgICAgICByZXR1cm4gaCArIHQKICAgICAgICB9CiAgICB9CiAgICByZXR1cm4gdAp9CmZ1bmN0aW9uIGdldGtleShpZCl7CnI9IkE0RjIxMERGRUY5RUEwNUQ1MTdFMEMzOENCQjlCQUU1QkNGNjQ2MzlFRDcxMTIwRjVCRENFMjRBQzIyNzBFMjBBQzRBQzQwMjlBOTUxRDM3MzgyMDc2MEVGRTZFRTI1Mzk5NDNCQzQwN0IwQ0Q5NjgwM0I1RDA3RURFRkUxODUwNDhENzY5NUEzMzhDNjJEREY0QTc1NzZEMjBCRDJBNjRGRjU0MDBEOTIwMjlGNDgzODNEN0RCMDFFOUJDQzMwMkZDQ0JGQzVDMkYzNjQxMzM3OEE5RUVERDQ3OTlFRDZDMERCNkQ0ODJDMUFCQUZERDNFQUIyQURBMTdGODczRTNDMTlEN0IzQzExMEVFQTlDODFENEI4N0RBMUFCNDY2M0VDNTVDNUFBMTdCRTVFQ0NGRjMyNTEwNDI5Rjc1OTM5NUJCMzdFRUIzMkU0RDcxQ0FEMEE1RDBBOEQ1NjU3QjAwRDREQTUyREQ3RTkxOENGQkRFQTlFRDFGODA0MDI0Nzc3ODVEMzdEOUJBRTBDRTI2NTJGOUQ1NjdCQ0JGMzcyNjdCNTExQzg0NUQ5ODU3Njg3RkE5NTAwMkIwNEQ4QjFCQjRGQUJFOUUyREVDMUNDRTE1M0QxOUUwRUI5Q0ZGOTI3QkMxNEI2MjUwMTI2NjNGODI5N0E2RTFGMEQ3RDZGIjsKaSA9ICIxMDAwMSI7CnMgPSBuZXcgUlNBS2V5OwpzLnNldFB1YmxpYyhyLCBpKTsKdCA9IHMuZW5jcnlwdChpZCk7CnJldHVybiB0Owp9ClNlY3VyZVJhbmRvbS5wcm90b3R5cGUubmV4dEJ5dGVzID0gcm5nX2dldF9ieXRlcywKUlNBS2V5LnByb3RvdHlwZS5kb1B1YmxpYyA9IFJTQURvUHVibGljLApSU0FLZXkucHJvdG90eXBlLnNldFB1YmxpYyA9IFJTQVNldFB1YmxpYywKUlNBS2V5LnByb3RvdHlwZS5lbmNyeXB0ID0gUlNBRW5jcnlwdDsK"
    js = base64.b64decode(js).decode('utf-8')

    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    }

    def gettotpkey(self, key, method=0)->str:
        """
        获取totp的6位动态口令
        Args:
            key: 生成totp的秘钥
            method: 0为使用pyotp库,1为使用接口
        Returns:
            6位动态口令，失败返回000000
        """
        if method == 0:
            # pyotp
            totp = pyotp.TOTP(key)
            return totp.now()
        elif method == 1:
            # 接口
            try:
                res = requests.post("http://www.2fafb.com/api/jiekou.php",data={"tok":key},headers=self.header)
                if res.status_code != 200:
                    return "000000"
                data = json.loads(res.text)
                #print(data)
                return data['data']
            except Exception as e:
                print(e)
                return "000000"
        else:
            return "000000"
    def getpwds(self, pwd:str,rand:str)->str: 
        """
        利用页面中原有js基础上，添加Function，实现对密码原文进行rsa加密，获取登录需要的svpn_pwd

        pwd 密码明文

        rand 请求config页面返回的随机数
        """
        id = "_".join([pwd,rand]) #pwd_rand
        ctx = execjs.compile(self.js)
        result = ctx.call("getkey",id)
        return result
class webvpn:
    def __init__(self, name:str, password:str, key:str,twfid=""):
        """
        Args:
            name: 用户名
            password: 密码
            key: 动态口令秘钥
            twfid: 如果有twfid则不需要登录，直接使用twfid进行登录
        """
        self.session = requests.Session()
        self.session.trust_env =True
        self.session.verify = False
        self.session.cookies.update({"TWFID": twfid})

        self.name = name
        self.password = password
        self.key = key
        self.twfid = twfid

        self.encrypt = encrypt()
        self.header = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "content-type": "application/x-www-form-urlencoded",
            "sec-ch-ua": "\"Not)A;Brand\";v=\"99\", \"Microsoft Edge\";v=\"127\", \"Chromium\";v=\"127\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
            "sec-fetch-site": "same-origin"
        }
    def autoLogin(self):
        """
        如果twfid能用则直接使用twfid登录，否则使用用户名和密码登录
        """
        if not self.getState():
            self.login()
            return self.getState()
        return True

    def login(self):
        # 需要使用会话来保持登录状态
        # 第一步：获取 CSRF_RAND_CODE 和 TwfID
        url_auth = 'https://webvpn.stu.edu.cn/por/login_auth.csp?apiversion=1'
        response_auth = self.session.get(url_auth,headers=self.header)
        if response_auth.status_code != 200:
            return "访问webvpn失败,请检查是否连接WiFi"
        xml_data = response_auth.content
        root = etree.fromstring(xml_data)
        csrf_rand_code = root.find('.//CSRF_RAND_CODE').text
        twfid = root.find('.//TwfID').text

        # 第二步：登录
        url_login = 'https://webvpn.stu.edu.cn/por/login_psw.csp?anti_replay=1&encrypt=1&apiversion=1'
        pwd2 = self.encrypt.getpwds(self.password,csrf_rand_code)

        data_login = {
            'mitm_result': '',  
            'svpn_req_randcode': csrf_rand_code,
            'svpn_name': self.name,  
            'svpn_password': pwd2,  
            'svpn_rand_code': ''  
        }

        response_login = self.session.post(url_login, data=data_login,headers=self.header)
        if response_login.status_code != 200:
            return "可能多次输入错密码出现了验证码，请自己手动登录一次webvpn"
        elif response_login.text.find("锁定") != -1:
            return "认证错误次数过多，被系统锁定"
        # 第三步：输入动态口令,需要绑定了数盾otp
        passkey = self.encrypt.gettotpkey(self.key)
        url_token = 'https://webvpn.stu.edu.cn/auth/token?apiversion=1'
        data_token = {
            'twfid': twfid,
            'svpn_inputtoken': passkey 
        }
        response_token = self.session.post(url_token, data=data_token,headers=self.header)
        if response_token.status_code != 200:
            return "动态口令错误，请检查key是否正确"
        cookies = self.session.cookies
        cookies_v = ""
        for co in cookies:
            if(co.name == "TWFID"):
                cookies_v = co.value
        if cookies_v == "":
            return "未成功获取到TWFID，请检查key是否输入正确"
        self.twfid = cookies_v

        return cookies_v  
    def getState(self):
        r = self.session.get("https://webvpn.stu.edu.cn/por/conf.csp?apiversion=1",headers=self.header)
        if r.status_code == 200:
            return "unexpected user service" not in r.content.decode() # 检测是否是在登录页面
        else:
            return False
    def create_url(self,url)->str:
        if not self.getState():
            self.login()
        return f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.twfid}&url={get_vpn_url(url)}"
def GtoM(b):
    b = b.replace("M", "")
    if b.find("G") != -1:
        b = b.replace("G", "")
        b = str(float(b) * 1024)
    return b
def get_data(put) -> tuple[float,float]:
    """
    根据流量请求包，分割流量数据
    :param put:
    :return:
    """
    data = re.findall("<tr> <td>([^<]*)</td> <td>([^<]*)", put)
    limit = 0.0
    now = 0.0
    for a, b in data:
        if a.find("流量额") != -1:
            limit = float(GtoM(b))
        elif a.find("当天") != -1:
            now = float(GtoM(b))
    return limit, now
def get_vpn_url(site)->str:
    """
    格式：xxx://xxxx(:xxx)(/xxx)
    """
    if "webvpn.stu.edu.cn:8118" in site:
        return site
    ret = re.match("([a-zA-z]+://)([^/]*)(/.*)", site, re.I)
    if ret is None:
        ret = re.match("([a-zA-z]+://)([^/]*)(/.*)", site + "/", re.I)
        if ret is None:
            return ""

    web = ret.group(2).replace('-','--').replace(".","-")
    if ":" in web:
        web = web.replace(":","-")+"-p"
    web = ret.group(1)+web
    if "https" not in web:
        return web+".webvpn.stu.edu.cn:8118"+ret.group(3)
    return web.replace("https","http")+"-s.webvpn.stu.edu.cn:8118"+ret.group(3)
def extract_text(text, start_marker, end_marker):
    pattern = re.compile(fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}', re.DOTALL)
    match = pattern.search(text)
    return match.group(1).strip() if match else None
class wifi(QObject):

    class state:
        """
        wifi的状态类
        """

        def __init__(self, state:str="未登录", total:float=0, used:float=0, name:str="未登录"):
            """
            Args:
                state: wifi的状态
                total: 总流量/G
                used: 已使用流量/G
            """
            self.state = state
            self.total = total
            self.used = used
            self.name = name
        def __str__(self):
            return {'state' : self.state,
                    'total' : self.total,
                    'used' : self.used,
                    'name':self.name}.__str__()
        def __repr__(self):
            return {'state' : self.state,
                    'total' : self.total,
                    'used' : self.used,
                    'name':self.name}.__repr__()
    __state = None
    state_update: Signal = Signal(state)
    flux_update:Signal = Signal(float,float)
    def __init__(self, name:str, password:str):
        """
        Args:
            name: 用户名
            password: 密码
        """
        super().__init__()
        self.name = name
        self.password = password

        self.session = requests.Session()
        self.session.trust_env =True
        self.session.verify = False
        #self.state = "未登录"

        self.url = "https://a.stu.edu.cn/ac_portal/login.php"
        self.header = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"   
        }
    def logout(self):
        """
        注销登录
        """
        r = self.session.post(self.url, headers=self.header, data="opr=logout&ipv4or6=")
        if r.status_code == 200:
            return r.content.decode()
        else:
            return "注销失败，请检查网络连接"
    def change_account(self,name,password):
        self.name = name
        self.password = password
        return self.login()
    def login(self)->bool:
        print(self.logout())
        r = self.session.post(self.url, headers=self.header, data=f"opr=pwdLogin&userName={self.name}&pwd={self.password}&ipv4or6=&rememberPwd=1")
        self.__state = self.getState()
        if r.status_code == 200:
            msg = r.content.decode()
            if "logon success" in msg or "已在线" in msg:
                #self.state ="登陆成功"
                return True
            elif "NOAUTH" in msg:
                #self.state = "无限流时间"
                return True
            elif "冻结" in msg:
                #self.state = "登陆失败，登录频繁，账户被冻结一分钟"
                return False
            #else:
                #self.state = "登陆失败，可能是密码错误"
        #else:
            #self.state = "登陆失败，请检查网络连接"
        return False

    def getState(self)-> state:
        """
        获取当前登录状态    
        """
        state = self.state()


        r = self.session.post("https://a.stu.edu.cn/ac_portal/userflux",headers=self.header)
        if r.status_code == 200:
            try:
                ret = r.content.decode()
            except UnicodeDecodeError:
                state.state = "未登录"
                state.total = 0
                state.used = 0
                self.state_update.emit(state)
                self.flux_update.emit(state.total, state.used)
                return state
            if "临时" in ret:
                state.state = "无限流"
                state.total = 999
                state.used = 0
                state.name = "<UNK>"
            elif "请求剩余流量时出错" in ret:
                state.state = "已登录"
                state.total = 0
                state.used = 0
                state.name = self.name
            else:
                state.state = "已登录"
                state.name = self.name
                state.total,state.used = get_data(ret)
        else:
            state.state = "未登录"
            state.total = 0
            state.used = 0

        self.state_update.emit(state)
        self.flux_update.emit(state.total, state.used)
        return state
# if __name__ == "__main__":
#
#     twfid = "1c1341a18a0223dd"
#     print(twfid)
#     #a = webvpn("","","",twfid)
#     print(a.autoLogin())
#     print(a.twfid)
#     import webbrowser
#     url = a.create_url(get_vpn_url("https://www.baidu.com"))
#     webbrowser.open(url)
class live_bilibili:
    def __init__(self, twfid:str=""):
        """
        Args:
            twfid: TWFID
        """
        self.session = requests.Session()
        self.session.trust_env =True
        self.session.verify = False
        self.twfid = twfid
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
        }

    def set_twfid(self,twfid:str):
        self.twfid = twfid

    def get_live_url(self,bili_url:str)->list:
        url = []
        res = self.session.get(
            bili_url,
            verify=False, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"},
            cookies={"TWFID": self.twfid}, timeout=3000)

        if res.status_code == 200:
            print("请求成功！")
            data = res.content.decode()
            j = json.loads(extract_text(data, 'window.__NEPTUNE_IS_MY_WAIFU__=', '</script>'))
            streams = j['roomInitRes']['data']['playurl_info']['playurl']['stream']

            for i, stream in enumerate(streams):
                for j, format_in in enumerate(stream['format']):
                    for k, codec in enumerate(format_in['codec']):
                        for l, url_info in enumerate(codec['url_info']):
                            url.append(url_info['host'] + codec['base_url'] + url_info['extra'])
                            #print(f"第{len(url)}个视频地址：http://hlsplayer-net-s.webvpn.stu.edu.cn:8118/embed?type=m3u8&src={url[-1]}")

        return url