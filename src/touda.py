
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
from src.logging_config import logger
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
    js_code = "d2luZG93PXt9O25hdmlnYXRvcj17fTt2YXIgZGJpdHMsIGNhbmFyeSA9IDB4ZGVhZGJlZWZjYWZlLCBqX2xtID0gMTU3MTUwNzAgPT0gKDE2Nzc3MjE1ICYgY2FuYXJ5KTsNCmZ1bmN0aW9uIEJpZ0ludGVnZXIodCwgciwgaSkgew0KICAgIG51bGwgIT0gdCAmJiAoIm51bWJlciIgPT0gdHlwZW9mIHQgPyB0aGlzLmZyb21OdW1iZXIodCwgciwgaSkgOiBudWxsID09IHIgJiYgInN0cmluZyIgIT0gdHlwZW9mIHQgPyB0aGlzLmZyb21TdHJpbmcodCwgMjU2KSA6IHRoaXMuZnJvbVN0cmluZyh0LCByKSkNCn0NCmZ1bmN0aW9uIG5iaSgpIHsNCiAgICByZXR1cm4gbmV3IEJpZ0ludGVnZXIobnVsbCkNCn0NCmZ1bmN0aW9uIGFtMSh0LCByLCBpLCBuLCBvLCBlKSB7DQogICAgZm9yICg7IDAgPD0gLS1lOyApIHsNCiAgICAgICAgdmFyIHMgPSByICogdGhpc1t0KytdICsgaVtuXSArIG87DQogICAgICAgIG8gPSBNYXRoLmZsb29yKHMgLyA2NzEwODg2NCksDQogICAgICAgIGlbbisrXSA9IDY3MTA4ODYzICYgcw0KICAgIH0NCiAgICByZXR1cm4gbw0KfQ0KZnVuY3Rpb24gYW0yKHQsIHIsIGksIG4sIG8sIGUpIHsNCiAgICBmb3IgKHZhciBzID0gMzI3NjcgJiByLCBoID0gciA+PiAxNTsgMCA8PSAtLWU7ICkgew0KICAgICAgICB2YXIgcCA9IDMyNzY3ICYgdGhpc1t0XQ0KICAgICAgICAgICwgZyA9IHRoaXNbdCsrXSA+PiAxNQ0KICAgICAgICAgICwgdSA9IGggKiBwICsgZyAqIHM7DQogICAgICAgIG8gPSAoKHAgPSBzICogcCArICgoMzI3NjcgJiB1KSA8PCAxNSkgKyBpW25dICsgKDEwNzM3NDE4MjMgJiBvKSkgPj4+IDMwKSArICh1ID4+PiAxNSkgKyBoICogZyArIChvID4+PiAzMCksDQogICAgICAgIGlbbisrXSA9IDEwNzM3NDE4MjMgJiBwDQogICAgfQ0KICAgIHJldHVybiBvDQp9DQpmdW5jdGlvbiBhbTModCwgciwgaSwgbiwgbywgZSkgew0KICAgIGZvciAodmFyIHMgPSAxNjM4MyAmIHIsIGggPSByID4+IDE0OyAwIDw9IC0tZTsgKSB7DQogICAgICAgIHZhciBwID0gMTYzODMgJiB0aGlzW3RdDQogICAgICAgICAgLCBnID0gdGhpc1t0KytdID4+IDE0DQogICAgICAgICAgLCB1ID0gaCAqIHAgKyBnICogczsNCiAgICAgICAgbyA9ICgocCA9IHMgKiBwICsgKCgxNjM4MyAmIHUpIDw8IDE0KSArIGlbbl0gKyBvKSA+PiAyOCkgKyAodSA+PiAxNCkgKyBoICogZywNCiAgICAgICAgaVtuKytdID0gMjY4NDM1NDU1ICYgcA0KICAgIH0NCiAgICByZXR1cm4gbw0KfQ0Kal9sbSAmJiAiTWljcm9zb2Z0IEludGVybmV0IEV4cGxvcmVyIiA9PSBuYXZpZ2F0b3IuYXBwTmFtZSA/IChCaWdJbnRlZ2VyLnByb3RvdHlwZS5hbSA9IGFtMiwNCmRiaXRzID0gMzApIDogal9sbSAmJiAiTmV0c2NhcGUiICE9IG5hdmlnYXRvci5hcHBOYW1lID8gKEJpZ0ludGVnZXIucHJvdG90eXBlLmFtID0gYW0xLA0KZGJpdHMgPSAyNikgOiAoQmlnSW50ZWdlci5wcm90b3R5cGUuYW0gPSBhbTMsDQpkYml0cyA9IDI4KSwNCkJpZ0ludGVnZXIucHJvdG90eXBlLkRCID0gZGJpdHMsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5ETSA9ICgxIDw8IGRiaXRzKSAtIDEsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5EViA9IDEgPDwgZGJpdHM7DQp2YXIgQklfRlAgPSA1MjsNCkJpZ0ludGVnZXIucHJvdG90eXBlLkZWID0gTWF0aC5wb3coMiwgQklfRlApLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuRjEgPSBCSV9GUCAtIGRiaXRzLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuRjIgPSAyICogZGJpdHMgLSBCSV9GUDsNCnZhciByciwgdnYsIEJJX1JNID0gIjAxMjM0NTY3ODlhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eiIsIEJJX1JDID0gbmV3IEFycmF5Ow0KZm9yIChyciA9ICIwIi5jaGFyQ29kZUF0KDApLA0KdnYgPSAwOyB2diA8PSA5OyArK3Z2KQ0KICAgIEJJX1JDW3JyKytdID0gdnY7DQpmb3IgKHJyID0gImEiLmNoYXJDb2RlQXQoMCksDQp2diA9IDEwOyB2diA8IDM2OyArK3Z2KQ0KICAgIEJJX1JDW3JyKytdID0gdnY7DQpmb3IgKHJyID0gIkEiLmNoYXJDb2RlQXQoMCksDQp2diA9IDEwOyB2diA8IDM2OyArK3Z2KQ0KICAgIEJJX1JDW3JyKytdID0gdnY7DQpmdW5jdGlvbiBpbnQyY2hhcih0KSB7DQogICAgcmV0dXJuIEJJX1JNLmNoYXJBdCh0KQ0KfQ0KZnVuY3Rpb24gaW50QXQodCwgcikgew0KICAgIHZhciBpID0gQklfUkNbdC5jaGFyQ29kZUF0KHIpXTsNCiAgICByZXR1cm4gbnVsbCA9PSBpID8gLTEgOiBpDQp9DQpmdW5jdGlvbiBibnBDb3B5VG8odCkgew0KICAgIGZvciAodmFyIHIgPSB0aGlzLnQgLSAxOyAwIDw9IHI7IC0tcikNCiAgICAgICAgdFtyXSA9IHRoaXNbcl07DQogICAgdC50ID0gdGhpcy50LA0KICAgIHQucyA9IHRoaXMucw0KfQ0KZnVuY3Rpb24gYm5wRnJvbUludCh0KSB7DQogICAgdGhpcy50ID0gMSwNCiAgICB0aGlzLnMgPSB0IDwgMCA/IC0xIDogMCwNCiAgICAwIDwgdCA/IHRoaXNbMF0gPSB0IDogdCA8IC0xID8gdGhpc1swXSA9IHQgKyB0aGlzLkRWIDogdGhpcy50ID0gMA0KfQ0KZnVuY3Rpb24gbmJ2KHQpIHsNCiAgICB2YXIgciA9IG5iaSgpOw0KICAgIHJldHVybiByLmZyb21JbnQodCksDQogICAgcg0KfQ0KZnVuY3Rpb24gYm5wRnJvbVN0cmluZyh0LCByKSB7DQogICAgdmFyIGk7DQogICAgaWYgKDE2ID09IHIpDQogICAgICAgIGkgPSA0Ow0KICAgIGVsc2UgaWYgKDggPT0gcikNCiAgICAgICAgaSA9IDM7DQogICAgZWxzZSBpZiAoMjU2ID09IHIpDQogICAgICAgIGkgPSA4Ow0KICAgIGVsc2UgaWYgKDIgPT0gcikNCiAgICAgICAgaSA9IDE7DQogICAgZWxzZSBpZiAoMzIgPT0gcikNCiAgICAgICAgaSA9IDU7DQogICAgZWxzZSB7DQogICAgICAgIGlmICg0ICE9IHIpDQogICAgICAgICAgICByZXR1cm4gdm9pZCB0aGlzLmZyb21SYWRpeCh0LCByKTsNCiAgICAgICAgaSA9IDINCiAgICB9DQogICAgdGhpcy50ID0gMCwNCiAgICB0aGlzLnMgPSAwOw0KICAgIGZvciAodmFyIG4gPSB0Lmxlbmd0aCwgbyA9ICExLCBlID0gMDsgMCA8PSAtLW47ICkgew0KICAgICAgICB2YXIgcyA9IDggPT0gaSA/IDI1NSAmIHRbbl0gOiBpbnRBdCh0LCBuKTsNCiAgICAgICAgcyA8IDAgPyAiLSIgPT0gdC5jaGFyQXQobikgJiYgKG8gPSAhMCkgOiAobyA9ICExLA0KICAgICAgICAwID09IGUgPyB0aGlzW3RoaXMudCsrXSA9IHMgOiBlICsgaSA+IHRoaXMuREIgPyAodGhpc1t0aGlzLnQgLSAxXSB8PSAocyAmICgxIDw8IHRoaXMuREIgLSBlKSAtIDEpIDw8IGUsDQogICAgICAgIHRoaXNbdGhpcy50KytdID0gcyA+PiB0aGlzLkRCIC0gZSkgOiB0aGlzW3RoaXMudCAtIDFdIHw9IHMgPDwgZSwNCiAgICAgICAgKGUgKz0gaSkgPj0gdGhpcy5EQiAmJiAoZSAtPSB0aGlzLkRCKSkNCiAgICB9DQogICAgOCA9PSBpICYmIDAgIT0gKDEyOCAmIHRbMF0pICYmICh0aGlzLnMgPSAtMSwNCiAgICAwIDwgZSAmJiAodGhpc1t0aGlzLnQgLSAxXSB8PSAoMSA8PCB0aGlzLkRCIC0gZSkgLSAxIDw8IGUpKSwNCiAgICB0aGlzLmNsYW1wKCksDQogICAgbyAmJiBCaWdJbnRlZ2VyLlpFUk8uc3ViVG8odGhpcywgdGhpcykNCn0NCmZ1bmN0aW9uIGJucENsYW1wKCkgew0KICAgIGZvciAodmFyIHQgPSB0aGlzLnMgJiB0aGlzLkRNOyAwIDwgdGhpcy50ICYmIHRoaXNbdGhpcy50IC0gMV0gPT0gdDsgKQ0KICAgICAgICAtLXRoaXMudA0KfQ0KZnVuY3Rpb24gYm5Ub1N0cmluZyh0KSB7DQogICAgaWYgKHRoaXMucyA8IDApDQogICAgICAgIHJldHVybiAiLSIgKyB0aGlzLm5lZ2F0ZSgpLnRvU3RyaW5nKHQpOw0KICAgIHZhciByOw0KICAgIGlmICgxNiA9PSB0KQ0KICAgICAgICByID0gNDsNCiAgICBlbHNlIGlmICg4ID09IHQpDQogICAgICAgIHIgPSAzOw0KICAgIGVsc2UgaWYgKDIgPT0gdCkNCiAgICAgICAgciA9IDE7DQogICAgZWxzZSBpZiAoMzIgPT0gdCkNCiAgICAgICAgciA9IDU7DQogICAgZWxzZSB7DQogICAgICAgIGlmICg0ICE9IHQpDQogICAgICAgICAgICByZXR1cm4gdGhpcy50b1JhZGl4KHQpOw0KICAgICAgICByID0gMg0KICAgIH0NCiAgICB2YXIgaSwgbiA9ICgxIDw8IHIpIC0gMSwgbyA9ICExLCBlID0gIiIsIHMgPSB0aGlzLnQsIGggPSB0aGlzLkRCIC0gcyAqIHRoaXMuREIgJSByOw0KICAgIGlmICgwIDwgcy0tKQ0KICAgICAgICBmb3IgKGggPCB0aGlzLkRCICYmIDAgPCAoaSA9IHRoaXNbc10gPj4gaCkgJiYgKG8gPSAhMCwNCiAgICAgICAgZSA9IGludDJjaGFyKGkpKTsgMCA8PSBzOyApDQogICAgICAgICAgICBoIDwgciA/IChpID0gKHRoaXNbc10gJiAoMSA8PCBoKSAtIDEpIDw8IHIgLSBoLA0KICAgICAgICAgICAgaSB8PSB0aGlzWy0tc10gPj4gKGggKz0gdGhpcy5EQiAtIHIpKSA6IChpID0gdGhpc1tzXSA+PiAoaCAtPSByKSAmIG4sDQogICAgICAgICAgICBoIDw9IDAgJiYgKGggKz0gdGhpcy5EQiwNCiAgICAgICAgICAgIC0tcykpLA0KICAgICAgICAgICAgMCA8IGkgJiYgKG8gPSAhMCksDQogICAgICAgICAgICBvICYmIChlICs9IGludDJjaGFyKGkpKTsNCiAgICByZXR1cm4gbyA/IGUgOiAiMCINCn0NCmZ1bmN0aW9uIGJuTmVnYXRlKCkgew0KICAgIHZhciB0ID0gbmJpKCk7DQogICAgcmV0dXJuIEJpZ0ludGVnZXIuWkVSTy5zdWJUbyh0aGlzLCB0KSwNCiAgICB0DQp9DQpmdW5jdGlvbiBibkFicygpIHsNCiAgICByZXR1cm4gdGhpcy5zIDwgMCA/IHRoaXMubmVnYXRlKCkgOiB0aGlzDQp9DQpmdW5jdGlvbiBibkNvbXBhcmVUbyh0KSB7DQogICAgdmFyIHIgPSB0aGlzLnMgLSB0LnM7DQogICAgaWYgKDAgIT0gcikNCiAgICAgICAgcmV0dXJuIHI7DQogICAgdmFyIGkgPSB0aGlzLnQ7DQogICAgaWYgKDAgIT0gKHIgPSBpIC0gdC50KSkNCiAgICAgICAgcmV0dXJuIHRoaXMucyA8IDAgPyAtciA6IHI7DQogICAgZm9yICg7IDAgPD0gLS1pOyApDQogICAgICAgIGlmICgwICE9IChyID0gdGhpc1tpXSAtIHRbaV0pKQ0KICAgICAgICAgICAgcmV0dXJuIHI7DQogICAgcmV0dXJuIDANCn0NCmZ1bmN0aW9uIG5iaXRzKHQpIHsNCiAgICB2YXIgciwgaSA9IDE7DQogICAgcmV0dXJuIDAgIT0gKHIgPSB0ID4+PiAxNikgJiYgKHQgPSByLA0KICAgIGkgKz0gMTYpLA0KICAgIDAgIT0gKHIgPSB0ID4+IDgpICYmICh0ID0gciwNCiAgICBpICs9IDgpLA0KICAgIDAgIT0gKHIgPSB0ID4+IDQpICYmICh0ID0gciwNCiAgICBpICs9IDQpLA0KICAgIDAgIT0gKHIgPSB0ID4+IDIpICYmICh0ID0gciwNCiAgICBpICs9IDIpLA0KICAgIDAgIT0gKHIgPSB0ID4+IDEpICYmICh0ID0gciwNCiAgICBpICs9IDEpLA0KICAgIGkNCn0NCmZ1bmN0aW9uIGJuQml0TGVuZ3RoKCkgew0KICAgIHJldHVybiB0aGlzLnQgPD0gMCA/IDAgOiB0aGlzLkRCICogKHRoaXMudCAtIDEpICsgbmJpdHModGhpc1t0aGlzLnQgLSAxXSBeIHRoaXMucyAmIHRoaXMuRE0pDQp9DQpmdW5jdGlvbiBibnBETFNoaWZ0VG8odCwgcikgew0KICAgIHZhciBpOw0KICAgIGZvciAoaSA9IHRoaXMudCAtIDE7IDAgPD0gaTsgLS1pKQ0KICAgICAgICByW2kgKyB0XSA9IHRoaXNbaV07DQogICAgZm9yIChpID0gdCAtIDE7IDAgPD0gaTsgLS1pKQ0KICAgICAgICByW2ldID0gMDsNCiAgICByLnQgPSB0aGlzLnQgKyB0LA0KICAgIHIucyA9IHRoaXMucw0KfQ0KZnVuY3Rpb24gYm5wRFJTaGlmdFRvKHQsIHIpIHsNCiAgICBmb3IgKHZhciBpID0gdDsgaSA8IHRoaXMudDsgKytpKQ0KICAgICAgICByW2kgLSB0XSA9IHRoaXNbaV07DQogICAgci50ID0gTWF0aC5tYXgodGhpcy50IC0gdCwgMCksDQogICAgci5zID0gdGhpcy5zDQp9DQpmdW5jdGlvbiBibnBMU2hpZnRUbyh0LCByKSB7DQogICAgdmFyIGksIG4gPSB0ICUgdGhpcy5EQiwgbyA9IHRoaXMuREIgLSBuLCBlID0gKDEgPDwgbykgLSAxLCBzID0gTWF0aC5mbG9vcih0IC8gdGhpcy5EQiksIGggPSB0aGlzLnMgPDwgbiAmIHRoaXMuRE07DQogICAgZm9yIChpID0gdGhpcy50IC0gMTsgMCA8PSBpOyAtLWkpDQogICAgICAgIHJbaSArIHMgKyAxXSA9IHRoaXNbaV0gPj4gbyB8IGgsDQogICAgICAgIGggPSAodGhpc1tpXSAmIGUpIDw8IG47DQogICAgZm9yIChpID0gcyAtIDE7IDAgPD0gaTsgLS1pKQ0KICAgICAgICByW2ldID0gMDsNCiAgICByW3NdID0gaCwNCiAgICByLnQgPSB0aGlzLnQgKyBzICsgMSwNCiAgICByLnMgPSB0aGlzLnMsDQogICAgci5jbGFtcCgpDQp9DQpmdW5jdGlvbiBibnBSU2hpZnRUbyh0LCByKSB7DQogICAgci5zID0gdGhpcy5zOw0KICAgIHZhciBpID0gTWF0aC5mbG9vcih0IC8gdGhpcy5EQik7DQogICAgaWYgKGkgPj0gdGhpcy50KQ0KICAgICAgICByLnQgPSAwOw0KICAgIGVsc2Ugew0KICAgICAgICB2YXIgbiA9IHQgJSB0aGlzLkRCDQogICAgICAgICAgLCBvID0gdGhpcy5EQiAtIG4NCiAgICAgICAgICAsIGUgPSAoMSA8PCBuKSAtIDE7DQogICAgICAgIHJbMF0gPSB0aGlzW2ldID4+IG47DQogICAgICAgIGZvciAodmFyIHMgPSBpICsgMTsgcyA8IHRoaXMudDsgKytzKQ0KICAgICAgICAgICAgcltzIC0gaSAtIDFdIHw9ICh0aGlzW3NdICYgZSkgPDwgbywNCiAgICAgICAgICAgIHJbcyAtIGldID0gdGhpc1tzXSA+PiBuOw0KICAgICAgICAwIDwgbiAmJiAoclt0aGlzLnQgLSBpIC0gMV0gfD0gKHRoaXMucyAmIGUpIDw8IG8pLA0KICAgICAgICByLnQgPSB0aGlzLnQgLSBpLA0KICAgICAgICByLmNsYW1wKCkNCiAgICB9DQp9DQpmdW5jdGlvbiBibnBTdWJUbyh0LCByKSB7DQogICAgZm9yICh2YXIgaSA9IDAsIG4gPSAwLCBvID0gTWF0aC5taW4odC50LCB0aGlzLnQpOyBpIDwgbzsgKQ0KICAgICAgICBuICs9IHRoaXNbaV0gLSB0W2ldLA0KICAgICAgICByW2krK10gPSBuICYgdGhpcy5ETSwNCiAgICAgICAgbiA+Pj0gdGhpcy5EQjsNCiAgICBpZiAodC50IDwgdGhpcy50KSB7DQogICAgICAgIGZvciAobiAtPSB0LnM7IGkgPCB0aGlzLnQ7ICkNCiAgICAgICAgICAgIG4gKz0gdGhpc1tpXSwNCiAgICAgICAgICAgIHJbaSsrXSA9IG4gJiB0aGlzLkRNLA0KICAgICAgICAgICAgbiA+Pj0gdGhpcy5EQjsNCiAgICAgICAgbiArPSB0aGlzLnMNCiAgICB9IGVsc2Ugew0KICAgICAgICBmb3IgKG4gKz0gdGhpcy5zOyBpIDwgdC50OyApDQogICAgICAgICAgICBuIC09IHRbaV0sDQogICAgICAgICAgICByW2krK10gPSBuICYgdGhpcy5ETSwNCiAgICAgICAgICAgIG4gPj49IHRoaXMuREI7DQogICAgICAgIG4gLT0gdC5zDQogICAgfQ0KICAgIHIucyA9IG4gPCAwID8gLTEgOiAwLA0KICAgIG4gPCAtMSA/IHJbaSsrXSA9IHRoaXMuRFYgKyBuIDogMCA8IG4gJiYgKHJbaSsrXSA9IG4pLA0KICAgIHIudCA9IGksDQogICAgci5jbGFtcCgpDQp9DQpmdW5jdGlvbiBibnBNdWx0aXBseVRvKHQsIHIpIHsNCiAgICB2YXIgaSA9IHRoaXMuYWJzKCkNCiAgICAgICwgbiA9IHQuYWJzKCkNCiAgICAgICwgbyA9IGkudDsNCiAgICBmb3IgKHIudCA9IG8gKyBuLnQ7IDAgPD0gLS1vOyApDQogICAgICAgIHJbb10gPSAwOw0KICAgIGZvciAobyA9IDA7IG8gPCBuLnQ7ICsrbykNCiAgICAgICAgcltvICsgaS50XSA9IGkuYW0oMCwgbltvXSwgciwgbywgMCwgaS50KTsNCiAgICByLnMgPSAwLA0KICAgIHIuY2xhbXAoKSwNCiAgICB0aGlzLnMgIT0gdC5zICYmIEJpZ0ludGVnZXIuWkVSTy5zdWJUbyhyLCByKQ0KfQ0KZnVuY3Rpb24gYm5wU3F1YXJlVG8odCkgew0KICAgIGZvciAodmFyIHIgPSB0aGlzLmFicygpLCBpID0gdC50ID0gMiAqIHIudDsgMCA8PSAtLWk7ICkNCiAgICAgICAgdFtpXSA9IDA7DQogICAgZm9yIChpID0gMDsgaSA8IHIudCAtIDE7ICsraSkgew0KICAgICAgICB2YXIgbiA9IHIuYW0oaSwgcltpXSwgdCwgMiAqIGksIDAsIDEpOw0KICAgICAgICAodFtpICsgci50XSArPSByLmFtKGkgKyAxLCAyICogcltpXSwgdCwgMiAqIGkgKyAxLCBuLCByLnQgLSBpIC0gMSkpID49IHIuRFYgJiYgKHRbaSArIHIudF0gLT0gci5EViwNCiAgICAgICAgdFtpICsgci50ICsgMV0gPSAxKQ0KICAgIH0NCiAgICAwIDwgdC50ICYmICh0W3QudCAtIDFdICs9IHIuYW0oaSwgcltpXSwgdCwgMiAqIGksIDAsIDEpKSwNCiAgICB0LnMgPSAwLA0KICAgIHQuY2xhbXAoKQ0KfQ0KZnVuY3Rpb24gYm5wRGl2UmVtVG8odCwgciwgaSkgew0KICAgIHZhciBuID0gdC5hYnMoKTsNCiAgICBpZiAoIShuLnQgPD0gMCkpIHsNCiAgICAgICAgdmFyIG8gPSB0aGlzLmFicygpOw0KICAgICAgICBpZiAoby50IDwgbi50KQ0KICAgICAgICAgICAgcmV0dXJuIG51bGwgIT0gciAmJiByLmZyb21JbnQoMCksDQogICAgICAgICAgICB2b2lkIChudWxsICE9IGkgJiYgdGhpcy5jb3B5VG8oaSkpOw0KICAgICAgICBudWxsID09IGkgJiYgKGkgPSBuYmkoKSk7DQogICAgICAgIHZhciBlID0gbmJpKCkNCiAgICAgICAgICAsIHMgPSB0aGlzLnMNCiAgICAgICAgICAsIGggPSB0LnMNCiAgICAgICAgICAsIHAgPSB0aGlzLkRCIC0gbmJpdHMobltuLnQgLSAxXSk7DQogICAgICAgIDAgPCBwID8gKG4ubFNoaWZ0VG8ocCwgZSksDQogICAgICAgIG8ubFNoaWZ0VG8ocCwgaSkpIDogKG4uY29weVRvKGUpLA0KICAgICAgICBvLmNvcHlUbyhpKSk7DQogICAgICAgIHZhciBnID0gZS50DQogICAgICAgICAgLCB1ID0gZVtnIC0gMV07DQogICAgICAgIGlmICgwICE9IHUpIHsNCiAgICAgICAgICAgIHZhciBhID0gdSAqICgxIDw8IHRoaXMuRjEpICsgKDEgPCBnID8gZVtnIC0gMl0gPj4gdGhpcy5GMiA6IDApDQogICAgICAgICAgICAgICwgZiA9IHRoaXMuRlYgLyBhDQogICAgICAgICAgICAgICwgbCA9ICgxIDw8IHRoaXMuRjEpIC8gYQ0KICAgICAgICAgICAgICAsIGMgPSAxIDw8IHRoaXMuRjINCiAgICAgICAgICAgICAgLCBtID0gaS50DQogICAgICAgICAgICAgICwgdiA9IG0gLSBnDQogICAgICAgICAgICAgICwgYiA9IG51bGwgPT0gciA/IG5iaSgpIDogcjsNCiAgICAgICAgICAgIGZvciAoZS5kbFNoaWZ0VG8odiwgYiksDQogICAgICAgICAgICAwIDw9IGkuY29tcGFyZVRvKGIpICYmIChpW2kudCsrXSA9IDEsDQogICAgICAgICAgICBpLnN1YlRvKGIsIGkpKSwNCiAgICAgICAgICAgIEJpZ0ludGVnZXIuT05FLmRsU2hpZnRUbyhnLCBiKSwNCiAgICAgICAgICAgIGIuc3ViVG8oZSwgZSk7IGUudCA8IGc7ICkNCiAgICAgICAgICAgICAgICBlW2UudCsrXSA9IDA7DQogICAgICAgICAgICBmb3IgKDsgMCA8PSAtLXY7ICkgew0KICAgICAgICAgICAgICAgIHZhciB5ID0gaVstLW1dID09IHUgPyB0aGlzLkRNIDogTWF0aC5mbG9vcihpW21dICogZiArIChpW20gLSAxXSArIGMpICogbCk7DQogICAgICAgICAgICAgICAgaWYgKChpW21dICs9IGUuYW0oMCwgeSwgaSwgdiwgMCwgZykpIDwgeSkNCiAgICAgICAgICAgICAgICAgICAgZm9yIChlLmRsU2hpZnRUbyh2LCBiKSwNCiAgICAgICAgICAgICAgICAgICAgaS5zdWJUbyhiLCBpKTsgaVttXSA8IC0teTsgKQ0KICAgICAgICAgICAgICAgICAgICAgICAgaS5zdWJUbyhiLCBpKQ0KICAgICAgICAgICAgfQ0KICAgICAgICAgICAgbnVsbCAhPSByICYmIChpLmRyU2hpZnRUbyhnLCByKSwNCiAgICAgICAgICAgIHMgIT0gaCAmJiBCaWdJbnRlZ2VyLlpFUk8uc3ViVG8ociwgcikpLA0KICAgICAgICAgICAgaS50ID0gZywNCiAgICAgICAgICAgIGkuY2xhbXAoKSwNCiAgICAgICAgICAgIDAgPCBwICYmIGkuclNoaWZ0VG8ocCwgaSksDQogICAgICAgICAgICBzIDwgMCAmJiBCaWdJbnRlZ2VyLlpFUk8uc3ViVG8oaSwgaSkNCiAgICAgICAgfQ0KICAgIH0NCn0NCmZ1bmN0aW9uIGJuTW9kKHQpIHsNCiAgICB2YXIgciA9IG5iaSgpOw0KICAgIHJldHVybiB0aGlzLmFicygpLmRpdlJlbVRvKHQsIG51bGwsIHIpLA0KICAgIHRoaXMucyA8IDAgJiYgMCA8IHIuY29tcGFyZVRvKEJpZ0ludGVnZXIuWkVSTykgJiYgdC5zdWJUbyhyLCByKSwNCiAgICByDQp9DQpmdW5jdGlvbiBDbGFzc2ljKHQpIHsNCiAgICB0aGlzLm0gPSB0DQp9DQpmdW5jdGlvbiBjQ29udmVydCh0KSB7DQogICAgcmV0dXJuIHQucyA8IDAgfHwgMCA8PSB0LmNvbXBhcmVUbyh0aGlzLm0pID8gdC5tb2QodGhpcy5tKSA6IHQNCn0NCmZ1bmN0aW9uIGNSZXZlcnQodCkgew0KICAgIHJldHVybiB0DQp9DQpmdW5jdGlvbiBjUmVkdWNlKHQpIHsNCiAgICB0LmRpdlJlbVRvKHRoaXMubSwgbnVsbCwgdCkNCn0NCmZ1bmN0aW9uIGNNdWxUbyh0LCByLCBpKSB7DQogICAgdC5tdWx0aXBseVRvKHIsIGkpLA0KICAgIHRoaXMucmVkdWNlKGkpDQp9DQpmdW5jdGlvbiBjU3FyVG8odCwgcikgew0KICAgIHQuc3F1YXJlVG8ociksDQogICAgdGhpcy5yZWR1Y2UocikNCn0NCmZ1bmN0aW9uIGJucEludkRpZ2l0KCkgew0KICAgIGlmICh0aGlzLnQgPCAxKQ0KICAgICAgICByZXR1cm4gMDsNCiAgICB2YXIgdCA9IHRoaXNbMF07DQogICAgaWYgKDAgPT0gKDEgJiB0KSkNCiAgICAgICAgcmV0dXJuIDA7DQogICAgdmFyIHIgPSAzICYgdDsNCiAgICByZXR1cm4gMCA8IChyID0gKHIgPSAociA9IChyID0gciAqICgyIC0gKDE1ICYgdCkgKiByKSAmIDE1KSAqICgyIC0gKDI1NSAmIHQpICogcikgJiAyNTUpICogKDIgLSAoKDY1NTM1ICYgdCkgKiByICYgNjU1MzUpKSAmIDY1NTM1KSAqICgyIC0gdCAqIHIgJSB0aGlzLkRWKSAlIHRoaXMuRFYpID8gdGhpcy5EViAtIHIgOiAtcg0KfQ0KZnVuY3Rpb24gTW9udGdvbWVyeSh0KSB7DQogICAgdGhpcy5tID0gdCwNCiAgICB0aGlzLm1wID0gdC5pbnZEaWdpdCgpLA0KICAgIHRoaXMubXBsID0gMzI3NjcgJiB0aGlzLm1wLA0KICAgIHRoaXMubXBoID0gdGhpcy5tcCA+PiAxNSwNCiAgICB0aGlzLnVtID0gKDEgPDwgdC5EQiAtIDE1KSAtIDEsDQogICAgdGhpcy5tdDIgPSAyICogdC50DQp9DQpmdW5jdGlvbiBtb250Q29udmVydCh0KSB7DQogICAgdmFyIHIgPSBuYmkoKTsNCiAgICByZXR1cm4gdC5hYnMoKS5kbFNoaWZ0VG8odGhpcy5tLnQsIHIpLA0KICAgIHIuZGl2UmVtVG8odGhpcy5tLCBudWxsLCByKSwNCiAgICB0LnMgPCAwICYmIDAgPCByLmNvbXBhcmVUbyhCaWdJbnRlZ2VyLlpFUk8pICYmIHRoaXMubS5zdWJUbyhyLCByKSwNCiAgICByDQp9DQpmdW5jdGlvbiBtb250UmV2ZXJ0KHQpIHsNCiAgICB2YXIgciA9IG5iaSgpOw0KICAgIHJldHVybiB0LmNvcHlUbyhyKSwNCiAgICB0aGlzLnJlZHVjZShyKSwNCiAgICByDQp9DQpmdW5jdGlvbiBtb250UmVkdWNlKHQpIHsNCiAgICBmb3IgKDsgdC50IDw9IHRoaXMubXQyOyApDQogICAgICAgIHRbdC50KytdID0gMDsNCiAgICBmb3IgKHZhciByID0gMDsgciA8IHRoaXMubS50OyArK3IpIHsNCiAgICAgICAgdmFyIGkgPSAzMjc2NyAmIHRbcl0NCiAgICAgICAgICAsIG4gPSBpICogdGhpcy5tcGwgKyAoKGkgKiB0aGlzLm1waCArICh0W3JdID4+IDE1KSAqIHRoaXMubXBsICYgdGhpcy51bSkgPDwgMTUpICYgdC5ETTsNCiAgICAgICAgZm9yICh0W2kgPSByICsgdGhpcy5tLnRdICs9IHRoaXMubS5hbSgwLCBuLCB0LCByLCAwLCB0aGlzLm0udCk7IHRbaV0gPj0gdC5EVjsgKQ0KICAgICAgICAgICAgdFtpXSAtPSB0LkRWLA0KICAgICAgICAgICAgdFsrK2ldKysNCiAgICB9DQogICAgdC5jbGFtcCgpLA0KICAgIHQuZHJTaGlmdFRvKHRoaXMubS50LCB0KSwNCiAgICAwIDw9IHQuY29tcGFyZVRvKHRoaXMubSkgJiYgdC5zdWJUbyh0aGlzLm0sIHQpDQp9DQpmdW5jdGlvbiBtb250U3FyVG8odCwgcikgew0KICAgIHQuc3F1YXJlVG8ociksDQogICAgdGhpcy5yZWR1Y2UocikNCn0NCmZ1bmN0aW9uIG1vbnRNdWxUbyh0LCByLCBpKSB7DQogICAgdC5tdWx0aXBseVRvKHIsIGkpLA0KICAgIHRoaXMucmVkdWNlKGkpDQp9DQpmdW5jdGlvbiBibnBJc0V2ZW4oKSB7DQogICAgcmV0dXJuIDAgPT0gKDAgPCB0aGlzLnQgPyAxICYgdGhpc1swXSA6IHRoaXMucykNCn0NCmZ1bmN0aW9uIGJucEV4cCh0LCByKSB7DQogICAgaWYgKDQyOTQ5NjcyOTUgPCB0IHx8IHQgPCAxKQ0KICAgICAgICByZXR1cm4gQmlnSW50ZWdlci5PTkU7DQogICAgdmFyIGkgPSBuYmkoKQ0KICAgICAgLCBuID0gbmJpKCkNCiAgICAgICwgbyA9IHIuY29udmVydCh0aGlzKQ0KICAgICAgLCBlID0gbmJpdHModCkgLSAxOw0KICAgIGZvciAoby5jb3B5VG8oaSk7IDAgPD0gLS1lOyApDQogICAgICAgIGlmIChyLnNxclRvKGksIG4pLA0KICAgICAgICAwIDwgKHQgJiAxIDw8IGUpKQ0KICAgICAgICAgICAgci5tdWxUbyhuLCBvLCBpKTsNCiAgICAgICAgZWxzZSB7DQogICAgICAgICAgICB2YXIgcyA9IGk7DQogICAgICAgICAgICBpID0gbiwNCiAgICAgICAgICAgIG4gPSBzDQogICAgICAgIH0NCiAgICByZXR1cm4gci5yZXZlcnQoaSkNCn0NCmZ1bmN0aW9uIGJuTW9kUG93SW50KHQsIHIpIHsNCiAgICB2YXIgaTsNCiAgICByZXR1cm4gaSA9IHQgPCAyNTYgfHwgci5pc0V2ZW4oKSA/IG5ldyBDbGFzc2ljKHIpIDogbmV3IE1vbnRnb21lcnkociksDQogICAgdGhpcy5leHAodCwgaSkNCn0NCmZ1bmN0aW9uIEFyY2ZvdXIoKSB7DQogICAgdGhpcy5pID0gMCwNCiAgICB0aGlzLmogPSAwLA0KICAgIHRoaXMuUyA9IG5ldyBBcnJheQ0KfQ0KZnVuY3Rpb24gQVJDNGluaXQodCkgew0KICAgIHZhciByLCBpLCBuOw0KICAgIGZvciAociA9IDA7IHIgPCAyNTY7ICsrcikNCiAgICAgICAgdGhpcy5TW3JdID0gcjsNCiAgICBmb3IgKHIgPSBpID0gMDsgciA8IDI1NjsgKytyKQ0KICAgICAgICBpID0gaSArIHRoaXMuU1tyXSArIHRbciAlIHQubGVuZ3RoXSAmIDI1NSwNCiAgICAgICAgbiA9IHRoaXMuU1tyXSwNCiAgICAgICAgdGhpcy5TW3JdID0gdGhpcy5TW2ldLA0KICAgICAgICB0aGlzLlNbaV0gPSBuOw0KICAgIHRoaXMuaSA9IDAsDQogICAgdGhpcy5qID0gMA0KfQ0KZnVuY3Rpb24gQVJDNG5leHQoKSB7DQogICAgdmFyIHQ7DQogICAgcmV0dXJuIHRoaXMuaSA9IHRoaXMuaSArIDEgJiAyNTUsDQogICAgdGhpcy5qID0gdGhpcy5qICsgdGhpcy5TW3RoaXMuaV0gJiAyNTUsDQogICAgdCA9IHRoaXMuU1t0aGlzLmldLA0KICAgIHRoaXMuU1t0aGlzLmldID0gdGhpcy5TW3RoaXMual0sDQogICAgdGhpcy5TW3RoaXMual0gPSB0LA0KICAgIHRoaXMuU1t0ICsgdGhpcy5TW3RoaXMuaV0gJiAyNTVdDQp9DQpmdW5jdGlvbiBwcm5nX25ld3N0YXRlKCkgew0KICAgIHJldHVybiBuZXcgQXJjZm91cg0KfQ0KQ2xhc3NpYy5wcm90b3R5cGUuY29udmVydCA9IGNDb252ZXJ0LA0KQ2xhc3NpYy5wcm90b3R5cGUucmV2ZXJ0ID0gY1JldmVydCwNCkNsYXNzaWMucHJvdG90eXBlLnJlZHVjZSA9IGNSZWR1Y2UsDQpDbGFzc2ljLnByb3RvdHlwZS5tdWxUbyA9IGNNdWxUbywNCkNsYXNzaWMucHJvdG90eXBlLnNxclRvID0gY1NxclRvLA0KTW9udGdvbWVyeS5wcm90b3R5cGUuY29udmVydCA9IG1vbnRDb252ZXJ0LA0KTW9udGdvbWVyeS5wcm90b3R5cGUucmV2ZXJ0ID0gbW9udFJldmVydCwNCk1vbnRnb21lcnkucHJvdG90eXBlLnJlZHVjZSA9IG1vbnRSZWR1Y2UsDQpNb250Z29tZXJ5LnByb3RvdHlwZS5tdWxUbyA9IG1vbnRNdWxUbywNCk1vbnRnb21lcnkucHJvdG90eXBlLnNxclRvID0gbW9udFNxclRvLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuY29weVRvID0gYm5wQ29weVRvLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuZnJvbUludCA9IGJucEZyb21JbnQsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5mcm9tU3RyaW5nID0gYm5wRnJvbVN0cmluZywNCkJpZ0ludGVnZXIucHJvdG90eXBlLmNsYW1wID0gYm5wQ2xhbXAsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5kbFNoaWZ0VG8gPSBibnBETFNoaWZ0VG8sDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5kclNoaWZ0VG8gPSBibnBEUlNoaWZ0VG8sDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5sU2hpZnRUbyA9IGJucExTaGlmdFRvLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuclNoaWZ0VG8gPSBibnBSU2hpZnRUbywNCkJpZ0ludGVnZXIucHJvdG90eXBlLnN1YlRvID0gYm5wU3ViVG8sDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5tdWx0aXBseVRvID0gYm5wTXVsdGlwbHlUbywNCkJpZ0ludGVnZXIucHJvdG90eXBlLnNxdWFyZVRvID0gYm5wU3F1YXJlVG8sDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5kaXZSZW1UbyA9IGJucERpdlJlbVRvLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuaW52RGlnaXQgPSBibnBJbnZEaWdpdCwNCkJpZ0ludGVnZXIucHJvdG90eXBlLmlzRXZlbiA9IGJucElzRXZlbiwNCkJpZ0ludGVnZXIucHJvdG90eXBlLmV4cCA9IGJucEV4cCwNCkJpZ0ludGVnZXIucHJvdG90eXBlLnRvU3RyaW5nID0gYm5Ub1N0cmluZywNCkJpZ0ludGVnZXIucHJvdG90eXBlLm5lZ2F0ZSA9IGJuTmVnYXRlLA0KQmlnSW50ZWdlci5wcm90b3R5cGUuYWJzID0gYm5BYnMsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5jb21wYXJlVG8gPSBibkNvbXBhcmVUbywNCkJpZ0ludGVnZXIucHJvdG90eXBlLmJpdExlbmd0aCA9IGJuQml0TGVuZ3RoLA0KQmlnSW50ZWdlci5wcm90b3R5cGUubW9kID0gYm5Nb2QsDQpCaWdJbnRlZ2VyLnByb3RvdHlwZS5tb2RQb3dJbnQgPSBibk1vZFBvd0ludCwNCkJpZ0ludGVnZXIuWkVSTyA9IG5idigwKSwNCkJpZ0ludGVnZXIuT05FID0gbmJ2KDEpLA0KQXJjZm91ci5wcm90b3R5cGUuaW5pdCA9IEFSQzRpbml0LA0KQXJjZm91ci5wcm90b3R5cGUubmV4dCA9IEFSQzRuZXh0Ow0KdmFyIHJuZ19zdGF0ZSwgcm5nX3Bvb2wsIHJuZ19wcHRyLCBybmdfcHNpemUgPSAyNTY7DQpmdW5jdGlvbiBybmdfc2VlZF9pbnQodCkgew0KICAgIHJuZ19wb29sW3JuZ19wcHRyKytdIF49IDI1NSAmIHQsDQogICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gXj0gdCA+PiA4ICYgMjU1LA0KICAgIHJuZ19wb29sW3JuZ19wcHRyKytdIF49IHQgPj4gMTYgJiAyNTUsDQogICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gXj0gdCA+PiAyNCAmIDI1NSwNCiAgICBybmdfcHNpemUgPD0gcm5nX3BwdHIgJiYgKHJuZ19wcHRyIC09IHJuZ19wc2l6ZSkNCn0NCmZ1bmN0aW9uIHJuZ19zZWVkX3RpbWUoKSB7DQogICAgcm5nX3NlZWRfaW50KChuZXcgRGF0ZSkuZ2V0VGltZSgpKQ0KfQ0KaWYgKG51bGwgPT0gcm5nX3Bvb2wpIHsNCiAgICB2YXIgdDsNCiAgICBpZiAocm5nX3Bvb2wgPSBuZXcgQXJyYXksDQogICAgcm5nX3BwdHIgPSAwLA0KICAgIHdpbmRvdy5jcnlwdG8gJiYgd2luZG93LmNyeXB0by5nZXRSYW5kb21WYWx1ZXMpIHsNCiAgICAgICAgdmFyIHVhID0gbmV3IFVpbnQ4QXJyYXkoMzIpOw0KICAgICAgICBmb3IgKHdpbmRvdy5jcnlwdG8uZ2V0UmFuZG9tVmFsdWVzKHVhKSwNCiAgICAgICAgdCA9IDA7IHQgPCAzMjsgKyt0KQ0KICAgICAgICAgICAgcm5nX3Bvb2xbcm5nX3BwdHIrK10gPSB1YVt0XQ0KICAgIH0NCiAgICBpZiAoIk5ldHNjYXBlIiA9PSBuYXZpZ2F0b3IuYXBwTmFtZSAmJiBuYXZpZ2F0b3IuYXBwVmVyc2lvbiA8ICI1IiAmJiB3aW5kb3cuY3J5cHRvKSB7DQogICAgICAgIHZhciB6ID0gd2luZG93LmNyeXB0by5yYW5kb20oMzIpOw0KICAgICAgICBmb3IgKHQgPSAwOyB0IDwgei5sZW5ndGg7ICsrdCkNCiAgICAgICAgICAgIHJuZ19wb29sW3JuZ19wcHRyKytdID0gMjU1ICYgei5jaGFyQ29kZUF0KHQpDQogICAgfQ0KICAgIGZvciAoOyBybmdfcHB0ciA8IHJuZ19wc2l6ZTsgKQ0KICAgICAgICB0ID0gTWF0aC5mbG9vcig2NTUzNiAqIE1hdGgucmFuZG9tKCkpLA0KICAgICAgICBybmdfcG9vbFtybmdfcHB0cisrXSA9IHQgPj4+IDgsDQogICAgICAgIHJuZ19wb29sW3JuZ19wcHRyKytdID0gMjU1ICYgdDsNCiAgICBybmdfcHB0ciA9IDAsDQogICAgcm5nX3NlZWRfdGltZSgpDQp9DQpmdW5jdGlvbiBybmdfZ2V0X2J5dGUoKSB7DQogICAgaWYgKG51bGwgPT0gcm5nX3N0YXRlKSB7DQogICAgICAgIGZvciAocm5nX3NlZWRfdGltZSgpLA0KICAgICAgICAocm5nX3N0YXRlID0gcHJuZ19uZXdzdGF0ZSgpKS5pbml0KHJuZ19wb29sKSwNCiAgICAgICAgcm5nX3BwdHIgPSAwOyBybmdfcHB0ciA8IHJuZ19wb29sLmxlbmd0aDsgKytybmdfcHB0cikNCiAgICAgICAgICAgIHJuZ19wb29sW3JuZ19wcHRyXSA9IDA7DQogICAgICAgIHJuZ19wcHRyID0gMA0KICAgIH0NCiAgICByZXR1cm4gcm5nX3N0YXRlLm5leHQoKQ0KfQ0KZnVuY3Rpb24gcm5nX2dldF9ieXRlcyh0KSB7DQogICAgdmFyIHI7DQogICAgZm9yIChyID0gMDsgciA8IHQubGVuZ3RoOyArK3IpDQogICAgICAgIHRbcl0gPSBybmdfZ2V0X2J5dGUoKQ0KfQ0KZnVuY3Rpb24gU2VjdXJlUmFuZG9tKCkge30NCmZ1bmN0aW9uIHBhcnNlQmlnSW50KHQsIHIpIHsNCiAgICByZXR1cm4gbmV3IEJpZ0ludGVnZXIodCxyKQ0KfQ0KZnVuY3Rpb24gbGluZWJyayh0LCByKSB7DQogICAgZm9yICh2YXIgaSA9ICIiLCBuID0gMDsgbiArIHIgPCB0Lmxlbmd0aDsgKQ0KICAgICAgICBpICs9IHQuc3Vic3RyaW5nKG4sIG4gKyByKSArICJcbiIsDQogICAgICAgIG4gKz0gcjsNCiAgICByZXR1cm4gaSArIHQuc3Vic3RyaW5nKG4sIHQubGVuZ3RoKQ0KfQ0KZnVuY3Rpb24gYnl0ZTJIZXgodCkgew0KICAgIHJldHVybiB0IDwgMTYgPyAiMCIgKyB0LnRvU3RyaW5nKDE2KSA6IHQudG9TdHJpbmcoMTYpDQp9DQpmdW5jdGlvbiBwa2NzMXBhZDIodCwgcikgew0KICAgIGlmIChyIDwgdC5sZW5ndGggKyAxMSkNCiAgICAgICAgcmV0dXJuIGNvbnNvbGUgJiYgY29uc29sZS5lcnJvciAmJiBjb25zb2xlLmVycm9yKCJNZXNzYWdlIHRvbyBsb25nIGZvciBSU0EiKSwNCiAgICAgICAgbnVsbDsNCiAgICBmb3IgKHZhciBpID0gbmV3IEFycmF5LCBuID0gdC5sZW5ndGggLSAxOyAwIDw9IG4gJiYgMCA8IHI7ICkgew0KICAgICAgICB2YXIgbyA9IHQuY2hhckNvZGVBdChuLS0pOw0KICAgICAgICBvIDwgMTI4ID8gaVstLXJdID0gbyA6IDEyNyA8IG8gJiYgbyA8IDIwNDggPyAoaVstLXJdID0gNjMgJiBvIHwgMTI4LA0KICAgICAgICBpWy0tcl0gPSBvID4+IDYgfCAxOTIpIDogKGlbLS1yXSA9IDYzICYgbyB8IDEyOCwNCiAgICAgICAgaVstLXJdID0gbyA+PiA2ICYgNjMgfCAxMjgsDQogICAgICAgIGlbLS1yXSA9IG8gPj4gMTIgfCAyMjQpDQogICAgfQ0KICAgIGlbLS1yXSA9IDA7DQogICAgZm9yICh2YXIgZSA9IG5ldyBTZWN1cmVSYW5kb20sIHMgPSBuZXcgQXJyYXk7IDIgPCByOyApIHsNCiAgICAgICAgZm9yIChzWzBdID0gMDsgMCA9PSBzWzBdOyApDQogICAgICAgICAgICBlLm5leHRCeXRlcyhzKTsNCiAgICAgICAgaVstLXJdID0gc1swXQ0KICAgIH0NCiAgICByZXR1cm4gaVstLXJdID0gMiwNCiAgICBpWy0tcl0gPSAwLA0KICAgIG5ldyBCaWdJbnRlZ2VyKGkpDQp9DQpmdW5jdGlvbiBSU0FLZXkoKSB7DQogICAgdGhpcy5uID0gbnVsbCwNCiAgICB0aGlzLmUgPSAwLA0KICAgIHRoaXMuZCA9IG51bGwsDQogICAgdGhpcy5wID0gbnVsbCwNCiAgICB0aGlzLnEgPSBudWxsLA0KICAgIHRoaXMuZG1wMSA9IG51bGwsDQogICAgdGhpcy5kbXExID0gbnVsbCwNCiAgICB0aGlzLmNvZWZmID0gbnVsbA0KfQ0KZnVuY3Rpb24gUlNBU2V0UHVibGljKHQsIHIpIHsNCiAgICBudWxsICE9IHQgJiYgbnVsbCAhPSByICYmIDAgPCB0Lmxlbmd0aCAmJiAwIDwgci5sZW5ndGggPyAodGhpcy5uID0gcGFyc2VCaWdJbnQodCwgMTYpLA0KICAgIHRoaXMuZSA9IHBhcnNlSW50KHIsIDE2KSkgOiBhbGVydCgiSW52YWxpZCBSU0EgcHVibGljIGtleSIpDQp9DQpmdW5jdGlvbiBSU0FEb1B1YmxpYyh0KSB7DQogICAgcmV0dXJuIHQubW9kUG93SW50KHRoaXMuZSwgdGhpcy5uKQ0KfQ0KZnVuY3Rpb24gUlNBRW5jcnlwdCh0KSB7DQogICAgdmFyIHIgPSBwa2NzMXBhZDIodCwgdGhpcy5uLmJpdExlbmd0aCgpICsgNyA+PiAzKTsNCiAgICBpZiAobnVsbCA9PSByKQ0KICAgICAgICByZXR1cm4gbnVsbDsNCiAgICB2YXIgaSA9IHRoaXMuZG9QdWJsaWMocik7DQogICAgcmV0dXJuIG51bGwgPT0gaSA/IG51bGwgOiBGaXhFbmNyeXB0TGVuZ3RoKGkudG9TdHJpbmcoMTYpKQ0KfQ0KZnVuY3Rpb24gRml4RW5jcnlwdExlbmd0aCh0KSB7DQogICAgdmFyIHIsIGksIG4sIG8gPSB0Lmxlbmd0aCwgZSA9IFsxMjgsIDI1NiwgNTEyLCAxMDI0LCAyMDQ4LCA0MDk2XTsNCiAgICBmb3IgKGkgPSAwOyBpIDwgZS5sZW5ndGg7IGkrKykgew0KICAgICAgICBpZiAobyA9PT0gKHIgPSBlW2ldKSkNCiAgICAgICAgICAgIHJldHVybiB0Ow0KICAgICAgICBpZiAobyA8IHIpIHsNCiAgICAgICAgICAgIHZhciBzID0gciAtIG8NCiAgICAgICAgICAgICAgLCBoID0gIiI7DQogICAgICAgICAgICBmb3IgKG4gPSAwOyBuIDwgczsgbisrKQ0KICAgICAgICAgICAgICAgIGggKz0gIjAiOw0KICAgICAgICAgICAgcmV0dXJuIGggKyB0DQogICAgICAgIH0NCiAgICB9DQogICAgcmV0dXJuIHQNCn0NCmZ1bmN0aW9uIGdldGtleShpZCl7DQpyPSIjIyN0aGlzIyMjaXMjIyNyIyMjIjsNCmkgPSAiMTAwMDEiOw0KcyA9IG5ldyBSU0FLZXk7DQpzLnNldFB1YmxpYyhyLCBpKTsNCnQgPSBzLmVuY3J5cHQoaWQpOw0KcmV0dXJuIHQ7DQp9DQpTZWN1cmVSYW5kb20ucHJvdG90eXBlLm5leHRCeXRlcyA9IHJuZ19nZXRfYnl0ZXMsDQpSU0FLZXkucHJvdG90eXBlLmRvUHVibGljID0gUlNBRG9QdWJsaWMsDQpSU0FLZXkucHJvdG90eXBlLnNldFB1YmxpYyA9IFJTQVNldFB1YmxpYywNClJTQUtleS5wcm90b3R5cGUuZW5jcnlwdCA9IFJTQUVuY3J5cHQ7DQo="
    

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
                res = requests.post("http://www.2fafb.com/api/jiekou.php",data={"tok":key},headers=self.header, timeout=10)
                if res.status_code != 200:
                    return "000000"
                data = json.loads(res.text)
                return data['data']
            except Exception:
                logger.exception('gettotpkey 请求失败')
                return "000000"
        else:
            return "000000"
    def getpwds(self, pwd:str,rand:str,r:str)->str: 
        """
        利用页面中原有js基础上，添加Function，实现对密码原文进行rsa加密，获取登录需要的svpn_pwd

        pwd 密码明文

        rand 请求config页面返回的随机数
        """
        id = "_".join([pwd,rand]) #pwd_rand
        js = base64.b64decode(self.js_code).decode('utf-8').replace("###this###is###r###",r)
        ctx = execjs.compile(js)
        result = ctx.call("getkey",id)
        return result
class webvpn(QObject):
    twfid_update:Signal = Signal(str)
    def __init__(self, name:str, password:str, key:str,twfid=""):
        """
        Args:
            name: 用户名
            password: 密码
            key: 动态口令秘钥
            twfid: 如果有twfid则不需要登录，直接使用twfid进行登录
        """
        super().__init__()
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
        r = root.find(".//RSA_ENCRYPT_KEY").text

        # 第二步：登录
        url_login = 'https://webvpn.stu.edu.cn/por/login_psw.csp?anti_replay=1&encrypt=1&apiversion=1'
        pwd2 = self.encrypt.getpwds(self.password,csrf_rand_code,r)

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
        self.twfid_update.emit(self.twfid)
        logger.info(f"登录成功，TWFID: {self.twfid}")
        return cookies_v
    def getState(self):
        r = self.session.get("https://webvpn.stu.edu.cn/por/conf.csp?apiversion=1",headers=self.header)
        #print(r.content.decode())
        if r.status_code == 200:
            ret = "unexpected user service" not in r.content.decode() # 检测是否是在登录页面
            if not ret:
                self.session.cookies.clear_session_cookies()
                self.twfid = ""
                self.twfid_update.emit(self.twfid)
            return ret
        else:
            self.session.cookies.clear_session_cookies()
            self.twfid = ""
            self.twfid_update.emit(self.twfid)
            return False
    def create_url(self,url:str)->str:
        """
            创建webvpn访问链接
        """
        if not self.getState():
            self.login()
        return f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.twfid}&url={get_vpn_url(url)}"
    def create_redirect_url(self,url:str)->str:
        """
            用webvpn重定向访问链接
        """
        if not self.getState():
            self.login()
        return f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.twfid}&url={url}"
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
        logger.info(f"校园网注销:{self.logout()}")
        r = self.session.post(self.url, headers=self.header, data=f"opr=pwdLogin&userName={self.name}&pwd={self.password}&ipv4or6=&rememberPwd=1", timeout=10)
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
            logger.info("请求成功！")
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