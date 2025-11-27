from extras.scripts import *
from django.utils.text import slugify
from ipam.models import VLAN, Prefix, Role, IPAddress

class AvailablePrefix():
  prefixes = ""
  subnet = ""
  def __init__(self, *args, **kwargs):
    self.prefixes = kwargs['prefix']
    self.subnet = kwargs['subnet']
