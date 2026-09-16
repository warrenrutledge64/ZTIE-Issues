#!/bin/sh
# 1. Write buffer to test leakage
echo "ZTIE-EVIL-BUFFER-DATA" > /tmp/ztie-leak-test.txt
# 2. Fork to background to test strace -ff
(
  sleep 2
  (exec 3<>/dev/tcp/93.184.216.34/443) 2>/dev/null || true
) &
wait
