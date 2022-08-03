import meraki
import os
from datetime import date, datetime
import json
import base64
import requests

## GLOBAL VARS ##
JSON_DIR = '' # directory to store the json file of firmware versions
WP_USER = '' # WordPress username
WP_PW = '' # WordPress password
WP_URL = '' # WordPress post URL
MERAKI_API_KEY = os.environ.get(MERAKI_DASHBOARD_API_KEY) || '' # get API key from OS env var or add it here manually
MERAKI_NETWORK_ID = '' # Network ID that contains all the networks to check for new firmware


# checks if json file exists
def check_json():
    fileExists = os.path.exists(JSON_DIR)
    return fileExists

# makes comparison to the firmware file and the results of the firmware versions returned from the API call
def compare(previousFw, currentFw):
    newUpdates = False
    foundMatch = False
    firmwareDict = {}
    i = None

    for product in currentFw:
        for fwCategory in currentFw[product]:
            for numFw in currentFw[product][fwCategory]:
                if fwCategory in previousFw[product]:
                    for eachPrevFirmware in previousFw[product][fwCategory]:
                        if i is None:
                            i = 0
                        else:
                            i += 1
                        if numFw["firmwareVersion"] == eachPrevFirmware["firmwareVersion"]:
                            foundMatch = True
                            currentFw[product][fwCategory][i]["categoryDate"] = eachPrevFirmware["categoryDate"]
                            break #break if the firmware has already been updated
                    if not foundMatch:
                        if product not in firmwareDict:
                            firmwareDict[product] = {}
                        if fwCategory not in firmwareDict[product]:
                            firmwareDict[product][fwCategory] = []
                        firmwareDict[product][fwCategory].append(numFw)
                        newUpdates = True
                else:
                    if product not in firmwareDict:
                        firmwareDict[product] = {}
                    if fwCategory not in firmwareDict[product]:
                        firmwareDict[product][fwCategory] = []
                    firmwareDict[product][fwCategory].append(numFw)
                    newUpdates = True
                i = None
                foundMatch = False

    if newUpdates:
        return currentFw, firmwareDict
    else:
        return 0, 0


# creates an HTTP POST for creating a WordPress post of the new firmware
def write_post(title, description):
    user = WP_USER
    password = WP_PW
    url = WP_URL
    wp_connection = user + ':' + password
    token = base64.b64encode(wp_connection.encode())
    headers = {'Authorization': 'Basic ' + token.decode('utf-8')}

    post_title = title
    post_body = description
    post = {
        'title': post_title,
        'status': 'publish',
        'content': post_body,
        'author': '1',
        'format': 'standard'
    }

    wp_request = requests.post(url + '/posts', headers=headers, json=post)


# creates WordPress post components
def new_firmware(currentFw):
    for product in currentFw:
        for fwCategory in currentFw[product]:
            for eachFw in currentFw[product][fwCategory]:
                if eachFw["hasFirmware"]:
                    title = "A new " + fwCategory + " " + product + " firmware is now available on " + datetime.now().strftime('%a, %d %b %Y')
                    body = "A new " + fwCategory + " " + product + " firmware version is available. Firmware " + \
                                       eachFw["firmwareVersion"] + " was just released on " + \
                                       eachFw["firmwareReleaseDate"] + " and has been in this firmware category since " + \
                                       eachFw["categoryDate"].strftime('%Y-%m-%d') + "."

                    write_post(title, body)


# creates firmware json file
def build_rss(firmware, file=False, fwCompare=None):
    currentFirmware = {}
    changedFirmware = None
    for prodK, prodV in firmware["products"].items():
        currentFirmware[prodK] = {}
        for fwCategory in prodV["availableVersions"]:
            cat = fwCategory["releaseType"]
            if fwCategory["releaseType"] not in currentFirmware[prodK]:
                currentFirmware[prodK][cat] = []
            currentFirmware[prodK][cat].append({
                "firmwareVersion": fwCategory["shortName"],
                "firmwareReleaseDate": fwCategory["releaseDate"][:10],
                "categoryDate": date.today(),
                "hasFirmware": fwCategory["hasFirmware"]
            })

    if file:
        currentFirmware, changedFirmware = compare(fwCompare, currentFirmware)
    if changedFirmware is not None and changedFirmware != 0:
        new_firmware(changedFirmware)
    if currentFirmware != 0:
        with open(JSON_DIR, "w") as outjson:
            json.dump(currentFirmware, outjson, default=str, indent=4)


# modifies results of firmware API call to add descriptions to firmware that no longer is present for a particular category
def sanitize_current_firmware(currentFw):
    for product in currentFw["products"]:
        hasStable = False
        hasCandidate = False
        hasBeta = False
        for idx, iterFirmware in enumerate(currentFw["products"][product]["availableVersions"]):
            if "stable" in iterFirmware.values():
                hasStable = True
                currentFw["products"][product]["availableVersions"][idx]["hasFirmware"] = True
            if "candidate" in iterFirmware.values():
                hasCandidate = True
                currentFw["products"][product]["availableVersions"][idx]["hasFirmware"] = True
            if "beta" in iterFirmware.values():
                hasBeta = True
                currentFw["products"][product]["availableVersions"][idx]["hasFirmware"] = True
        if not hasStable:
            noStable = {"shortName": "No stable firmware available at this time",
                        "releaseType": "stable",
                        "releaseDate": datetime.now().strftime('%Y-%m-%d'),
                        "hasFirmware": False}
            currentFw["products"][product]["availableVersions"].append(noStable)
        if not hasCandidate:
            noCandidate = {"shortName": "No stable release candidate firmware available at this time",
                           "releaseType": "candidate",
                           "releaseDate": datetime.now().strftime('%Y-%m-%d'),
                           "hasFirmware": False}
            currentFw["products"][product]["availableVersions"].append(noCandidate)
        if not hasBeta:
            noBeta = {"shortName": "No beta firmware available at this time",
                      "releaseType": "beta",
                      "releaseDate": datetime.now().strftime('%Y-%m-%d'),
                      "hasFirmware": False}
            currentFw["products"][product]["availableVersions"].append(noBeta)

    return currentFw


# performs API GET call to acquire current firmware
def get_firmware():
    m = meraki.DashboardAPI(suppress_logging=True, api_key=MERAKI_API_KEY)
    firmware = m.networks.getNetworkFirmwareUpgrades(MERAKI_NETWORK_ID)
    firmware = sanitize_current_firmware(firmware)
    return firmware


# returns json file
def get_json():
    with open(JSON_DIR) as json_file:
        data = json.load(json_file)
    return data


def rss():
    isJsonFile = check_json()
    if (isJsonFile):
        prevFirmware = get_json()
        fw = get_firmware()
        build_rss(fw, isJsonFile, prevFirmware)
    else:
        fw = get_firmware()
        build_rss(fw, isJsonFile)


if __name__ == '__main__':
    rss()
