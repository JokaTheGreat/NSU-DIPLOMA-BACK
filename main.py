import xml.etree.ElementTree as ET
import re
import paramiko

from flask import Flask, request
from flask_cors import cross_origin

host = '0.0.0.0'
port = 3333

ssh_host = 'ftp_storage'
ssh_user = 'root'
ssh_pass = 'root'

xml_file_path = '/root/app/update_picks_workdir/temp.xml'

app = Flask(__name__)


def dump_xml_from_db(ssh_client, event_id):
    dump_xml_command = f"scxmldump -fpP -E {event_id} -o {xml_file_path} \
             -d postgresql://sysop:sysop@localhost/seiscomp"
    ssh_client.exec_command(dump_xml_command)


def update_xml(ssh_client, picks):
    with ssh_client.open_sftp() as sftp_client:
        with sftp_client.open(xml_file_path, mode="r") as remote_file:
            prefix = "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11"
            tree = ET.parse(remote_file)
            ET.register_namespace('', prefix)
            root = tree.getroot()

            xml_picks = root.find(f"{{{prefix}}}EventParameters").findall(f"{{{prefix}}}pick")

            for pick in picks:
                pick_id_regexp = r'^' + re.escape(pick["pickIdStart"]) + r'.*' + re.escape(
                    pick["pickIdEnd"]) + r'\.[A-Z]{3}$'
                for xml_pick in xml_picks:
                    if re.match(pick_id_regexp, xml_pick.get("publicID")):
                        xml_pick.find(f"{{{prefix}}}time").find(f"{{{prefix}}}value").text = str(pick["time"])

        with sftp_client.open(xml_file_path, mode="w") as remote_file:
            tree.write(remote_file, encoding='UTF-8', xml_declaration=True)


def write_xml_to_db(ssh_client):
    update_xml_command = f"scdispatch -i {xml_file_path} -O update"
    ssh_client.exec_command(update_xml_command)


def delete_temp_xml(ssh_client):
    delete_xml_command = f"rm {xml_file_path}"
    ssh_client.exec_command(delete_xml_command)


@app.route("/", methods=['POST'])
@cross_origin()
def update_pick_times():
    event_id = request.json["eventId"]
    picks = request.json["picks"]

    with paramiko.SSHClient() as ssh_client:
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ssh_host, username=ssh_user, password=ssh_pass)

        dump_xml_from_db(ssh_client, event_id)

        update_xml(ssh_client, picks)

        write_xml_to_db(ssh_client)

        delete_temp_xml(ssh_client)

    return request.json


if __name__ == "__main__":
    app.run(host=host, port=port, debug=True)
