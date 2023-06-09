[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://brands.home-assistant.io/_/echorobotics/dark_logo@2x.png">
  <img alt="Echorobotics Logo" src="https://brands.home-assistant.io/_/echorobotics/logo@2x.png">
</picture>

Echorobotics integration
========================

Reads status and allows control of Echorobotics robotic lawn mowers, such as the TM-1000, TM-1050, TM-2000 and TM-2050.
May also support Belrobotics mowers, they seem to be the same thing.

Getting the credentials
=======================

During setup the integration will ask for `user_id`, `user_token` and `robot_id`.
See the [Wiki page](https://github.com/functionpointer/home-assistant-echorobotics-integration/wiki/Getting-login-credentials) to learn how to get them.

Switch, guessed_mode and optimistic
===================================

The ``sensor`` and ``button`` entities are directly connected to the robot, without any special sauce.

By contrast, the ``switch`` entity is smart.
The fundamental challenge comes from the fact that the API does not report the operating mode ("work", "chargeAndWork", "chargeAndStay") of the robot,.
We can take a guess though, which is implemented by the smart_mode feature of pyechorobotics.

The Switch state depends on smart_mode. When toggling the switch, we have to wait for up to 25s until a response from the robot comes (use_current feature of pyechorobotics).
For an improved user experience, this integration features sort-of optimistic mode:

When the switch is pressed, the switch changes state immediately.
This is optimistic, and to show this the ``pending_modechange`` attribute is set.

Once the response comes, the state is changed again:
If the response is positive, the attribute will be cleared ("None").
If the response is negative, the switch state changes back, and the attribute is cleared.

This behaviour is particularly suited for a good visual indication using a [custom button card](https://github.com/custom-cards/button-card).

