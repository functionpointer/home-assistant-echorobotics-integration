Hacking
=======

Contains some developer documentation

Debug logs
==========

Add this to your configuration.yaml

````
logger:
  default: info
  logs:
    custom_components.echorobotics: debug
    echoroboticsapi: debug
````


Drafting a release
==================

1. Update [manifest.json](custom_components/echorobotics/manifest.json) with new version number
2. [Draft a new release](https://github.com/functionpointer/home-assistant-echorobotics-integration/releases/new) on GitHub  
    Choose vX.X.X as tag name, and type the changelog in

Installing a branch using HACS
==============================

See https://hacs.xyz/docs/use/entities/update/#install-action
