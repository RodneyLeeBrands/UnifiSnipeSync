# UniFi to Snipe-IT

This project is a Python script that synchronizes UniFi devices with Snipe-IT. It fetches devices from a UniFi controller, formats them, and adds or updates them in Snipe-IT. The script can also create new models in Snipe-IT if they don't already exist.

## Features

*   Fetch devices from UniFi controller
*   Fetch existing UniFi devices from Snipe-IT
*   Create new models in Snipe-IT if they don't already exist
*   Add new devices to Snipe-IT or update existing ones
*   Dry run mode to preview changes without modifying Snipe-IT

## Requirements

*   Python 3.6 or higher
*   `requests` library
*   `ratelimiter` library
*   `tabulate` library

## Installation


1.  Clone the repository or download the source code.

```
`git clone https://github.com/yourusername/unifi-to-snipeit.git cd unifi-to-snipeit`
```

2.  Install the required libraries.

```
pip3 install -r requirements.txt

```

3.  Copy `config_example.ini` to `config.ini` and update the configuration settings with your UniFi and Snipe-IT credentials and preferences.

```
cp config_example.ini config.ini
```

## Configuration


Update the `config.ini` file with your UniFi controller and Snipe-IT API credentials and preferences. The following sections are available for configuration:

*   `[UniFi]`: UniFi controller settings (URL, username, password, port, version, and site ID)
*   `[SnipeIT]`: Snipe-IT API settings (API URL, API key, manufacturer, model category ID, MAC address field name, default status ID, and rate limit)
*   `[unifi_model_mapping]`: UniFi model mapping for converting UniFi model names to Snipe-IT model names

### PyUnifi
We used the PyUnifi libary to interact with the Unifi API. You might want to read through their docs to debug your particular connection. We included a unifi.py file where you can test your settings. https://github.com/finish06/pyunifi


## Usage


To run the script, execute the following command:

```
python main.py
```

To perform a dry run without making changes to Snipe-IT, use the `--dry-run` option:

```
python main.py --dry-run
```

During the dry run, the script will output a summary of the changes that would be made to Snipe-IT.


Contributing
------------

Please feel free to open issues or submit pull requests with bug fixes or improvements. Your contributions are welcome and appreciated.

License
-------

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
