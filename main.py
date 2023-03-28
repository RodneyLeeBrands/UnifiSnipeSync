import warnings


import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from requests import Session

from pyunifi.controller import Controller
import configparser
from snipe import Snipe
import argparse
from termcolor import colored, cprint
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
            "serial": device.get("serial", ""),
            #"asset_tag": device.get("asset_tag", ""),
            #if an asset is a router, we want to get it's local IP address and not it's public ip. UXG at least, has a lan_ip feild that the other devices do not.
            "ip_address": device.get("lan_ip", device["ip"]),
        }
        formatted_devices.append(formatted_device)
    return formatted_devices

# Function to fetch all UniFi devices from Snipe-IT using the manufacturer filter
def fetch_unifi_devices_from_snipeit(manufacturer):
    params = {"manufacturer_id": manufacturer}
    return snipe.get_all_hardware(params=params)

# Function to check if a device exists in the fetched UniFi devices array using its MAC address
# Now returns the existing device if found
def device_exists_in_snipeit(serial, unifi_devices):
    for device in unifi_devices:
        #Unifi's serial numbers are just mac-addresses. We have stored the serial numbers in Snipe with XX:XX:XX:XX:XX:XX formatting. The Unifi API returns XXXXXXXXXXXX. To keep from having to update snipe, we are going to normalize the data.
        #strip snipe-it seriel of colon and make lowercase. 
        snipe_seriel = device["serial"].replace(':', '').lower() 

        if serial.lower() == snipe_seriel:
            return device
    return None

# Function to fetch all UniFi models from Snipe-IT
def fetch_unifi_models_from_snipeit(manufacturer_id):
    all_models = snipe.get_all_models()

    unifi_models = []

    for model in all_models:

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
        #add custom field to device for later use

        print("Checking device "+device['name']+" - ("+device['serial']+")")
       # print(device)
        existing_device = device_exists_in_snipeit(device["serial"], unifi_devices_in_snipe)
        remapped_model_number = unifi_model_mapping.get(device["model"], device["model"])
       # print("remapped_model_number", remapped_model_number)
        model = {
            "name": remapped_model_number,
            "manufacturer_id": config.get("SnipeIT", "unifi_manufacturer_id"),
            "model_number": remapped_model_number
        }
        model_in_snipeit = create_model_if_not_exists(model, unifi_models, dry_run)
        
        if model_in_snipeit:
            device["model_id"] = model_in_snipeit["id"]

        if existing_device:
            changeForDevice = {
                "Action": "",
                "Unifi Device Name": "",
                "Snipe Name": "",
                "Device Serial": "",
                "Device MAC": "",
                "Model": "",
                "Snipe-IT Model ID": "",
                "IP Address": ""
            }
            #Compare Unfi and Snipe-IT device data and determain if either needs to be updated
            snipeUpdateNeeded = False

            #check if device name is different
            if(device['name'] != existing_device['name']):
                device_name_priority = config.get('SnipeIT', 'device_name_priority')
                if(device_name_priority == "unifi"):
                    #we need to update Snipe-IT with the name set in Unifi
                    snipeUpdateNeeded = True 
                    print("device name needed changing");
                    changeForDevice['Unifi Device Name'] = device['name']
                    changeForDevice['Snipe Name'] = (f"\033[32m"+device['name']+"\033[0m ("+existing_device['name']+")")
                else:
                    #no change is needed, but we need to update the changeForDevice object
                    changeForDevice['Unifi Device Name'] = device['name']
                    changeForDevice['Snipe Name'] = existing_device['name']
            else:
                changeForDevice['Unifi Device Name'] = device['name']
                changeForDevice['Snipe Name'] = existing_device['name']
            
            #check if IP address needs to be updated
            ip_address_field_name = config.get('SnipeIT', 'ip_address_field_name')
            
            snipe_ip_address = ""
            for key, field in existing_device['custom_fields'].items():
                if field['field'] == ip_address_field_name:
                    snipe_ip_address = field['value']
                    break

            if(device['ip_address'] != snipe_ip_address):
                snipeUpdateNeeded = True
                print("device IP address needed changing");
                changeForDevice['IP Address'] = (f"\033[32m"+device['ip_address']+"\033[0m ("+snipe_ip_address+")")
                #add IP address to custom fields
                device[ip_address_field_name] = device['ip_address']
                
                
            else:
                changeForDevice['IP Address'] = device['ip_address']
            
            #check if mac address needs to be updated
            mac_address_field_name = config.get('SnipeIT', 'mac_address_field_name')
            
            snipe_mac_address = ""
            for key, field in existing_device['custom_fields'].items():
                if field['field'] == mac_address_field_name:
                    snipe_mac_address = field['value']
                    break

            if(device['mac_address'].lower() != snipe_mac_address.lower()):
                snipeUpdateNeeded = True
                print("device MAC address needed changing")
                changeForDevice['Device MAC'] = (f"\033[32m"+device['mac_address']+"\033[0m ("+snipe_mac_address.lower()+")")
                #add MAC address to custom fields
                device[mac_address_field_name] = device['mac_address']

            else:
                changeForDevice['Device MAC'] = device['mac_address']


            if(snipeUpdateNeeded):
                changeForDevice['Action'] = (f"\033[32m Update \033[0m")
                changeForDevice['Device Serial'] = device['serial']
                changeForDevice['Model'] = device['model']
                changeForDevice['Snipe-IT Model ID'] = device['model_id']
                changes.append(changeForDevice)
            else:
                changes.append({
                    "Action": (f"\033[33m Skipped \033[0m"),
                    "Unifi Device Name": (f"\033[33m "+ device["name"] +"\033[0m"),
                    "Snipe Name": (f"\033[33m "+ existing_device["name"] +"\033[0m"),
                    "Device Serial": (f"\033[33m "+ device["serial"] +"\033[0m"),
                    "Device MAC": (f"\033[33m "+ device["mac_address"] +"\033[0m"),
                    "Model": (f"\033[33m "+ device["model"] +"\033[0m"),
                    "Snipe-IT Model ID": (f"\033[33m "+ str(device["model_id"]) +"\033[0m"),
                    "IP Address": (f"\033[33m "+ device['ip_address'] +"\033[0m")
                })




            if not dry_run and snipeUpdateNeeded:
                
                response = snipe.update_hardware(existing_device["id"], device)
                print(f"Device {device['name']} updated in Snipe-IT. Status: {response.status_code}")
        else:
            #add device status to request
            device['status_id'] = config.get("SnipeIT", "default_status_id")
            #add empty asset tag to request
            # device['asset_tag'] = None
    
            changes.append({
                "Action": "Create",
                "Unifi Device Name": device["name"],
                "Device Serial": device["serial"],
                "Device MAC": device["mac_address"],
                "Model": device["model"],
                "Snipe-IT Model ID": device["model_id"],
                "IP Address": device['ip_address']
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
    parser.add_argument("--site-id", type=str, help="Override the site_id specified in the config file")
    args = parser.parse_args()
    controller = create_unifi_controller(
        config.get("UniFi", "controller_url"),
        config.get("UniFi", "username"),
        config.get("UniFi", "password"),
        config.getint("UniFi", "port"),
        config.get("UniFi", "version"),
        args.site_id if args.site_id else config.get("UniFi", "site_id"),
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
