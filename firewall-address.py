from extras.scripts import *
from django.utils.text import slugify
from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site
from ipam.models import IPAddress


class LinkFirewallToAddress(Script):
    class Meta:
        name = "Liaison Firewall-Adresses"
        description = "Permet de lier les Firewall à leurs adresses"

    def run(self, data, commit):
        devicerole=DeviceRole.objects.filter(name="Firewall")[0]
        firewalls=Device.objects.filter(role=devicerole.id)
        for firewall in firewalls:
            self.log_success(f"firewall found: {firewall.name},site {firewall.site}")
