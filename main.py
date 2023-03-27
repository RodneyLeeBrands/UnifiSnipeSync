import warnings


import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from requests import Session

from pyunifi.controller import Controller
import configparser
from snipe import Snipe
import argparse
from tabulate import tabulate


# Read configurations from config.ini
config = configparser.ConfigParser()
config.read("config.ini")

unifi_model_mapping = {v.lower(): k for k, v in config["unifi_model_mapping"].items()}
mac_address_field_name = config.get('SnipeIT', 'mac_address_field_name')

# Set up Snipe-IT API
snipe = Snipe(
    config.get("SnipeIT", "api_url"),
    config.get("SnipeIT", "api_key"),
    int(config.get("SnipeIT", "rate_limit")),
    30,
)


# Function to create a UniFi Controller instance
def create_unifi_controller(url, username, password, port, version, site_id, verify_ssl=False):
    return Controller(url, username, password, port, version, site_id, ssl_verify=verify_ssl)

# Function to fetch device information from the UniFi Controller
def fetch_devices(controller):
    return controller.get_aps()

# Function to process and format the device information
def format_devices_from_unifi(unifi_devices):
   
    formatted_devices = []
    for device in unifi_devices:
        #print(device)
        formatted_device = {
            "name": device.get("name", device["mac"]),
            "mac_address": device["mac"],
            "model": device["model"],
            "serial": device.get("serial", "")
            #"asset_tag": device.get("asset_tag", ""),
        }
        formatted_devices.append(formatted_device)
    return formatted_devices

# Function to fetch all UniFi devices from Snipe-IT using the manufacturer filter
def fetch_unifi_devices_from_snipeit(manufacturer):
    params = {"manufacturer_id": manufacturer}
    return snipe.get_all_hardware(params=params)

# Function to check if a device exists in the fetched UniFi devices array using its MAC address
# Now returns the existing device if found
def device_exists_in_snipeit(mac_address, unifi_devices):
    for device in unifi_devices:
        mac = None
        for key, field in device['custom_fields'].items():
            if field['field'] == mac_address_field_name:
                mac = field['value']
                break

        if mac.lower() == mac_address.lower():
            return device
    return None

# Function to fetch all UniFi models from Snipe-IT
def fetch_unifi_models_from_snipeit(manufacturer_id):
    all_models = snipe.get_all_models()

    unifi_models = []

    for model in all_models:
        print("checking model", model)
        if model.get('manufacturer') and int(model['manufacturer']['id']) == int(manufacturer_id):
            mapped_model = model.copy()
            mapped_model['model_number'] = unifi_model_mapping.get(model['model_number'].lower(), model['model_number'])
            unifi_models.append(mapped_model)
    return unifi_models

# Function to create a model in Snipe-IT if it doesn't exist
def create_model_if_not_exists(model, unifi_models, dry_run):
   
    if not any(existing_model["model_number"].lower() == model["model_number"].lower() for existing_model in unifi_models):
        if dry_run:
            print(f"Would create model: {model['model_number']}")
            placeholder_model = model.copy()
            placeholder_model['id'] = 'placeholder_id'
            return placeholder_model
        else:
            #add model category to request
            model['category_id'] = config.get("SnipeIT", "unifi_model_category_id")
            response = snipe.create_model(model)
            new_model_json = response.json()
            status = new_model_json.get("status")

            if status == "success":
                print(f"Model {model['model_number']} created in Snipe-IT. Status: {response.status_code}")
                # return the payload of the response
                return new_model_json.get('payload')
            else:
                print(f"Error creating model {model['model_number']} in Snipe-IT. Status: {response.status_code}")
                print(f"Error details: {new_model_json.get('messages')}")
                return None
    else:
        print(f"Model {model['model_number']} already exists in Snipe-IT. Skipping creation.")
        matching_models = [existing_model for existing_model in unifi_models if existing_model["model_number"].lower() == model["model_number"].lower()]
        return matching_models[0] if matching_models else None

# Function to add devices to Snipe-IT using its API
def add_devices_to_snipeit(devices, unifi_devices_in_snipe, dry_run):
    unifi_models = fetch_unifi_models_from_snipeit(config.get("SnipeIT", "unifi_manufacturer_id"))

    changes = []
    for device in devices:
        print("adding new device to snipeit")
       # print(device)
        existing_device = device_exists_in_snipeit(device["mac_address"], unifi_devices_in_snipe)
        remapped_model_number = unifi_model_mapping.get(device["model"], device["model"])
       # print("remapped_model_number", remapped_model_number)
        model = {
            "name": remapped_model_number,
            "manufacturer_id": config.get("SnipeIT", "unifi_manufacturer_id"),
            "model_number": remapped_model_number
        }
        model_in_snipeit = create_model_if_not_exists(model, unifi_models, dry_run)
        
        print("model_in_snipeit", model_in_snipeit)

        if model_in_snipeit:
            device["model_id"] = model_in_snipeit["id"]

        if existing_device:
            changes.append({
                "Action": "Update",
                "Device Name": device["name"],
                "Device MAC": device["mac_address"],
                "Model": device["model"],
                "Model ID": device["model_id"],
            })
            if not dry_run:
                response = snipe.update_hardware(existing_device["id"], device)
                print(f"Device {device['name']} updated in Snipe-IT. Status: {response.status_code}")
        else:
            #add device status to request
            device['status_id'] = config.get("SnipeIT", "default_status_id")
            #add empty asset tag to request
           # device['asset_tag'] = None
    
            changes.append({
                "Action": "Create",
                "Device Name": device["name"],
                "Device MAC": device["mac_address"],
                "Model": device["model"],
                "Model ID": device["model_id"],
            })


            if not dry_run:
                response = snipe.create_hardware(device)
                print(f"Device {device['name']} added to Snipe-IT. Status: {response.status_code}", response.json())

    if dry_run:
        print("Dry run summary:")
        print(tabulate(changes, headers="keys"))


# Main script
def main():
    parser = argparse.ArgumentParser(description="Unifi to Snipe-IT script")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without making changes to Snipe-IT")
    args = parser.parse_args()
    controller = create_unifi_controller(
        config.get("UniFi", "controller_url"),
        config.get("UniFi", "username"),
        config.get("UniFi", "password"),
        config.getint("UniFi", "port"),
        config.get("UniFi", "version"),
        config.get("UniFi", "site_id"),
    )
    unifi_devices = fetch_devices(controller)
    formatted_devices = format_devices_from_unifi(unifi_devices)

    if args.dry_run:
        print("Devices found in Unifi:")
        devices_table = [{
            "Device Name": device["name"],
            "Device MAC": device["mac_address"],
            "Model": device["model"],
        } for device in formatted_devices]
        print(tabulate(devices_table, headers="keys"))


    unifi_devices_in_snipeit = fetch_unifi_devices_from_snipeit(config.get("SnipeIT", "unifi_manufacturer_id"))
    add_devices_to_snipeit(formatted_devices, unifi_devices_in_snipeit, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
