#!/bin/bash
# 1. Write planted buffer (tests %desc)
printf 'ZTIE-EVIL-BUFFER-DATA-2p4R\n' > /tmp/ztie-write-probe.txt
# 2. File ops (tests %file)
for i in 1 2 3; do touch /tmp/ztie-probe-$i.txt; rm -f /tmp/ztie-probe-$i.txt; done
# 3. Real connect() intent (tests %network)
exec 3<>/dev/tcp/93.184.216.34/443 || true
