import pexpect
import sys
child = pexpect.spawn('./venv/bin/magia', encoding='utf-8')
child.logfile = sys.stdout
child.expect("Quel animé cherchez-vous ?")
child.sendline("wistoria")
child.expect("Que voulez-vous faire", timeout=15)
child.sendline("\x03")
