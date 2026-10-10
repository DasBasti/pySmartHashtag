# pySmartHashtag

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![CodeQL Validation][codeql-shield]][codeql]
[![Dependency Validation][tests-shield]][tests]

API wrapper for Smart #1, #3 and #5 Cloud Service

Regard this to be kind of stable. This library is used in custom [Homeassistant](https://homeassistant.io) component [Smart Hashtag](https://github.com/DasBasti/SmartHashtag)

Get this custom integration into homeassistant

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=smarthashtag)

[![Project Maintenance][maintenance-shield]](https://platinenmacher.tech)

## Credits

The Smart #5 seat comfort functions (ZAF request format) exist thanks to community contributors:

- [@radzatm](https://github.com/radzatm) captured the working ZAF seat heating request of the Smart #5 with a man-in-the-middle proxy and tested the debug builds ([SmartHashtag#478](https://github.com/DasBasti/SmartHashtag/issues/478)).
- [@ooooli](https://github.com/ooooli) documented and confirmed the ZAF request format for climate, seat heating, steering wheel heating and front seat ventilation ([SmartHashtag#479](https://github.com/DasBasti/SmartHashtag/issues/479)).
- [@krlimi69](https://github.com/krlimi69) reported the failing seat heating on the Smart #5 Brabus and tested the fixes ([SmartHashtag#478](https://github.com/DasBasti/SmartHashtag/issues/478)).

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
