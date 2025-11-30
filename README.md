# pySmartHashtag

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![CodeQL Validation][codeql-shield]][codeql]
[![Dependency Validation][tests-shield]][tests]

API wrapper for Smart #1 and #3 Cloud Service

Regard this to be kind of stable. This library is used in custom [Homeassistant](https://homeassistant.io) component [Smart Hashtag](https://github.com/DasBasti/SmartHashtag)

Get this custom integration into homeassistant

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=smarthashtag)

[![Project Maintenance][maintenance-shield]](https://platinenmacher.tech)

## Region Support

The library supports both European and International (Asia-Pacific) regions. This is important for users with the **Hello Smart International** app (used in Australia, Singapore, and other international markets).

### Usage

```python
from pysmarthashtag.account import SmartAccount
from pysmarthashtag.const import SmartRegion, get_endpoint_urls_for_region

# For European users (default)
account = SmartAccount("user@example.com", "password")

# For International/Asia-Pacific users (Australia, Singapore, etc.)
endpoint_urls = get_endpoint_urls_for_region(SmartRegion.INTL)
account = SmartAccount("user@example.com", "password", endpoint_urls=endpoint_urls)
```

### CLI Usage

When using the command-line interface, you can specify the region with the `--region` flag:

```bash
# European region (default)
python -m pysmarthashtag.cli --username user@example.com --password secret status

# International region
python -m pysmarthashtag.cli --username user@example.com --password secret --region intl status
```

You can also set the region via environment variable:

```bash
export SMART_REGION=intl
```

## AI Disclosure

This project uses AI to assist with development.

[license-shield]: https://img.shields.io/github/license/DasBasti/pysmarthashtag.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-Bastian%20Neumann%20%40DasBasti-blue.svg
[releases-shield]: https://img.shields.io/github/v/release/DasBasti/pysmarthashtag.svg
[releases]: https://github.com/DasBasti/pysmarthashtag/releases
[tests-shield]: https://github.com/DasBasti/SmartHashtag/actions/workflows/tests.yml/badge.svg
[tests]: https://github.com/DasBasti/pySmartHashtag/actions/workflows/python-package.yml
[codeql-shield]: https://github.com/DasBasti/smarthashtag/actions/workflows/codeql-analysis.yml/badge.svg
[codeql]: https://github.com/DasBasti/pySmartHashtag/actions/workflows/github-code-scanning/codeql
