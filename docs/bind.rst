Bind nsupdate Provider
======================

Provider configuration
----------------------

Define *bindns* as a provider of type bind::

  zbuilder config provider bindns type=bind
  zbuilder config provider bindns server=SERVER_IP
  zbuilder config provider bindns keyname=YOUR_KEYNAME
  zbuilder config provider bindns keysecret=YOUR_KEY_SECRET

  zbuilder config provider bindns.dns zones=bind.hasiotis.dev
  zbuilder config view
