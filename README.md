[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://brands.home-assistant.io/_/echorobotics/dark_logo@2x.png">
  <img alt="Echorobotics Logo" src="https://brands.home-assistant.io/_/echorobotics/logo@2x.png">
</picture>

Echorobotics integration
========================

Reads status and allows control of Echorobotics robotic lawn mowers, such as the TM-1000, TM-1050, TM-2000 and TM-2050.
May also support Belrobotics mowers, they seem to be the same thing.

Uses [pyechorobotics](https://github.com/functionpointer/pyechorobotics) under the hood.

Installation
============

Install like any other HACS custom repository.
1. Install [HACS](https://hacs.xyz/)
2. Add this repo as a custom repository: https://hacs.xyz/docs/faq/custom_repositories/
3. The integration should show up in HACS. Install it. Restart HA.
4. Go into your [integrations](https://my.home-assistant.io/redirect/integrations/) and add Echorobotics.

Getting the credentials
=======================

During setup the integration will ask for `user_id`, `user_token` and `robot_id`.
See the [Wiki page](https://github.com/functionpointer/home-assistant-echorobotics-integration/wiki/Getting-login-credentials) to learn how to get them.

Switch, guessed_mode and optimistic
===================================

The ``sensor`` and ``button`` entities are directly connected to the robot, without any special sauce.

By contrast, the auto-mow ``switch`` entity is smart.
The fundamental challenge comes from the fact that the API does not report the operating mode ("work", "chargeAndWork", "chargeAndStay") of the robot.
We can take a guess though, which is implemented by the smart_mode feature of pyechorobotics.

The Switch state depends on smart_mode. When toggling the switch, we have to wait for up to 25s until a response from the robot comes (use_current feature of pyechorobotics).
For an improved user experience, this integration features sort-of optimistic mode:

When the switch is pressed, the switch changes state immediately.
This is optimistic, and to show this the ``pending_modechange`` attribute is set.

Once the response comes, the state is changed again:
If the response is positive, the attribute will be cleared ("None").
If the response is negative, the switch state changes back, and the attribute is cleared.

custom-button-card example
==========================

The previously described behaviour particularly suited for a good visual indication using a [custom button card](https://github.com/custom-cards/button-card).
Turning on             |  On
:-------------------------:|:-------------------------:
![grafik](https://github.com/functionpointer/home-assistant-echorobotics-integration/assets/9073578/acae9a8f-8809-43b1-95c4-51a756423e02)  |  ![grafik](https://github.com/functionpointer/home-assistant-echorobotics-integration/assets/9073578/de8388b1-cdf3-4d33-a891-b2f2b991ea14)




Example:
````
type: custom:button-card
entity: switch.eepm000715
color_type: icon
tap_action:
  action: toggle
hold_action:
  action: none
double_tap_action:
  action: none
show_state: true
state:
  - operator: template
    value: >-
      [[[ return entity.attributes.pending_modechange === "work"
      || entity.attributes.pending_modechange ===
      "chargeAndWork" ]]]
    color: var(--deep-orange-color)
    state_display: Turning on...
    icon: mdi:satellite-uplink
  - operator: template
    value: >-
      [[[ return entity.attributes.pending_modechange ===
      "chargeAndStay" ]]]
    color: var(--deep-orange-color)
    state_display: Turning off...
    icon: mdi:satellite-uplink
  - value: 'on'
    color: var(--state-switch-active-color)
    state_display: On
  - value: 'off'
    color: var(--paper-item-icon-color)
    state_display: Off
show_label: true
name: Robot lawn mower
size: 100%
styles:
  card:
    - height: 230px
  label:
    - text-overflow: visible
    - white-space: normal
    - overflow: visible
    - margin-top: 10px
````

lawn_mower entity
=================

The ``lawn_mower`` entity maps the state ``sensor`` to homeassistant's built-in LawnMowerActivities ``MOWING``, ``DOCKED`` and ``ERROR``.
While docked, the entity does not tell you if the robot will start mowing again after charging completes.
For that, use the state from the auto-mow switch described above.
Pressing ``MOW`` or ``DOCK`` is equivalent to the button entities ``WORK`` and ``CHARGE AND STAY``.

Hacking
=======

See [hacking.md](hacking.md)
