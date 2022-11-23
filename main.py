import subprocess
import xml.etree.ElementTree as ET
import re

from flask import Flask, request
from flask_cors import cross_origin

host = '0.0.0.0'
port = 8080

app = Flask(__name__)


@app.route("/update-picks", methods=['POST'])
@cross_origin()
def update_pick_times():
    eventId = request.json["eventId"]
    picks = request.json["picks"]

    getXmlFromDBCommand = f"scxmldump -fpP -E {eventId} -o {eventId}.xml \
         -d postgresql://sysop:sysop@localhost/seiscomp"

    process = subprocess.Popen(getXmlFromDBCommand, stdout=subprocess.PIPE)
    process.wait()

    prefix = "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11"
    filename = f"{eventId}.xml"
    tree = ET.parse(filename)
    ET.register_namespace('', prefix)
    root = tree.getroot()

    xmlPicks = root.find(f"{{{prefix}}}EventParameters").findall(f"{{{prefix}}}pick")

    for pick in picks:
        regExp = r'^' + re.escape(pick["pickIdStart"]) + r'.*' + re.escape(pick["pickIdEnd"]) + r'\.[A-Z]{3}$'
        for xmlPick in xmlPicks:
            if (re.match(regExp, xmlPick.get("publicID"))):
                xmlPick.find(f"{{{prefix}}}time").find(f"{{{prefix}}}value").text = str(pick["time"])

    tree.write(filename, encoding='UTF-8', xml_declaration=True)
    updateXmlFromDBCommand = f"scdispatch -i {eventId}.xml -O update"

    process = subprocess.Popen(updateXmlFromDBCommand, stdout=subprocess.PIPE)
    process.wait()

    return request.json


@app.route('/hello')
def hello_world():
    return 'Hello, World!'


if __name__ == "__main__":
    app.run(host=host, port=port, debug=True)
