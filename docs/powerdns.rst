PHPipam Provider
===============

Provider configuration
----------------------

Define *pdns* as a provider of type powerdns::

  zbuilder config provider pdns type=powerdns
  zbuilder config provider pdns url=http://pdns.hasiotis.dev:8081/
  zbuilder config provider pdns apikey=YOURAPIKEY

  zbuilder config provider pdns.dns zones=pdns.hasiotis.dev
  zbuilder config view
