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
    stdin, stdout, stderr = ssh_client.exec_command(dump_xml_command)
    stdout.channel.recv_exit_status()


def create_new_xml_pick(pick_id, phase, time, network, station, channel):
    new_pick = ET.Element("pick")
    new_pick.set("publicID", str(pick_id))
    pick_phase = ET.SubElement(new_pick, "phaseHint")
    pick_phase.text = str(phase)
    pick_polarity = ET.SubElement(new_pick, "polarity")
    pick_polarity.text = "undecidable"
    pick_evaluation_mode = ET.SubElement(new_pick, "evaluationMode")
    pick_evaluation_mode.text = "manual"
    pick_time = ET.SubElement(new_pick, "time")
    pick_time_value = ET.SubElement(pick_time, "value")
    pick_time_value.text = str(time)
    pick_waveform_id = ET.SubElement(new_pick, "waveformID")
    pick_waveform_id.set("networkCode", str(network))
    pick_waveform_id.set("stationCode", str(station))
    pick_waveform_id.set("locationCode", "00")
    pick_waveform_id.set("channelCode", str(channel))
    pick_evaluation_status = ET.SubElement(new_pick, "evaluationStatus")
    pick_evaluation_status.text = "final"

    new_arrival = ET.Element("arrival")
    arrival_pick_id = ET.SubElement(new_arrival, "pickID")
    arrival_pick_id.text = str(pick_id)
    arrival_phase = ET.SubElement(new_arrival, "phase")
    arrival_phase.text = str(phase)

    return new_pick, new_arrival


def update_xml(ssh_client, picks, event_id):
    with ssh_client.open_sftp() as sftp_client:
        with sftp_client.open(xml_file_path, mode="r") as remote_file:
            prefix = "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11"
            tree = ET.parse(remote_file)
            ET.register_namespace('', prefix)
            root = tree.getroot()

            xml_picks = root.find(f"{{{prefix}}}EventParameters").findall(f"{{{prefix}}}pick")

            for pick in picks:
                pick_id_regexp = r'^' + re.escape(pick["pickId"]) + r'\.[A-Z]{3}$'
                is_xml_pick_doesnt_exist = True
                for xml_pick in xml_picks:
                    if re.match(pick_id_regexp, xml_pick.get("publicID")):
                        xml_pick.find(f"{{{prefix}}}time").find(f"{{{prefix}}}value").text = str(pick["time"])
                        is_xml_pick_doesnt_exist = False

                if is_xml_pick_doesnt_exist:
                    pick_hhz, arrival_hhz = create_new_xml_pick(pick["pickId"] + ".HHZ",
                                                            pick["phase"],
                                                            pick["time"], pick["network"],
                                                            pick["station"], "HHZ")
                    pick_hhn, arrival_hhn = create_new_xml_pick(pick["pickId"] + ".HHN",
                                                            pick["phase"],
                                                            pick["time"], pick["network"],
                                                            pick["station"], "HHN")
                    pick_hhe, arrival_hhe = create_new_xml_pick(pick["pickId"] + ".HHE",
                                                            pick["phase"],
                                                            pick["time"], pick["network"],
                                                            pick["station"], "HHE")
                    pick_parent_element = root.find(f"{{{prefix}}}EventParameters")
                    pick_parent_element.insert(0, pick_hhz)
                    pick_parent_element.insert(0, pick_hhn)
                    pick_parent_element.insert(0, pick_hhe)

                    arrival_parent_element = pick_parent_element.find(f"{{{prefix}}}origin")
                    arrival_parent_element.insert(0, arrival_hhz)
                    arrival_parent_element.insert(0, arrival_hhn)
                    arrival_parent_element.insert(0, arrival_hhe)

        with sftp_client.open(xml_file_path, mode="w") as remote_file:
            tree.write(remote_file, encoding='UTF-8', xml_declaration=True)


def write_xml_to_db(ssh_client):
    add_xml_command = f"scdispatch -i {xml_file_path} -O add"
    update_xml_command = f"scdispatch -i {xml_file_path} -O update"
    stdin, stdout, stderr = ssh_client.exec_command(add_xml_command)
    stdout.channel.recv_exit_status()
    stdin, stdout, stderr = ssh_client.exec_command(update_xml_command)
    stdout.channel.recv_exit_status()


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

        update_xml(ssh_client, picks, event_id)

        write_xml_to_db(ssh_client)

        delete_temp_xml(ssh_client)

    return request.json


if __name__ == "__main__":
    app.run(host=host, port=port, debug=True)
