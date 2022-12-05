import subprocess
import xml.etree.ElementTree as ET
import re
import paramiko

from flask import Flask, request
from flask_cors import cross_origin

host = '0.0.0.0'
port = 3333

sshHost = 'ftp_storage'
sshUser = 'root'
sshPassw = 'root'

app = Flask(__name__)


@app.route("/update-picks", methods=['POST'])
@cross_origin()
def update_pick_times():
    eventId = request.json["eventId"]
    picks = request.json["picks"]

    sshClient = paramiko.SSHClient()
    sshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshClient.connect(hostname=sshHost, username=sshUser, password=sshPassw)

    stdin, stdout, stderr = sshClient.exec_command(f"scxmldump -fpP -E {eventId} -o ./test/TEST.xml \
         -d postgresql://sysop:sysop@localhost/seiscomp")
    app.logger.info(str(stdout.read() + stderr.read(), 'utf-8'))

    prefix = "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11"
    filename = "./test/TEST.xml"
    sftpClient = sshClient.open_sftp()
    remoteFile = sftpClient.open(filename, mode="r")
    tree = ET.parse(remoteFile)
    ET.register_namespace('', prefix)
    root = tree.getroot()

    xmlPicks = root.find(f"{{{prefix}}}EventParameters").findall(f"{{{prefix}}}pick")

    for pick in picks:
        regExp = r'^' + re.escape(pick["pickIdStart"]) + r'.*' + re.escape(pick["pickIdEnd"]) + r'\.[A-Z]{3}$'
        for xmlPick in xmlPicks:
            if (re.match(regExp, xmlPick.get("publicID"))):
                xmlPick.find(f"{{{prefix}}}time").find(f"{{{prefix}}}value").text = str(pick["time"])

    remoteFile.close()
    remoteFile = sftpClient.open(filename, mode="w")
    tree.write(remoteFile, encoding='UTF-8', xml_declaration=True)
    updateXmlFromDBCommand = f"scdispatch -i {eventId}.xml -O update"

    remoteFile.close()

    stdin, stdout, stderr = sshClient.exec_command(f"scdispatch -i ./test/TEST.xml -O update")
    app.logger.info(str(stdout.read() + stderr.read(), 'utf-8'))

    sshClient.close()
    return request.json


@app.route('/hello')
def hello_world():
    return 'Hello, World!'


def sshConnection():
    sshClient = paramiko.SSHClient()
    sshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshClient.connect(hostname=sshHost, username=sshUser, password=sshPassw)

    while True:
        command = input()
        if command == "q":
            break
        stdin, stdout, stderr = sshClient.exec_command(command)
        print(str(stdout.read() + stderr.read(), 'utf-8'))

    sshClient.close()


if __name__ == "__main__":
    app.run(host=host, port=port, debug=True)

