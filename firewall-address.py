from extras.scripts import *
from django.utils.text import slugify
from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site
from ipam.models import IPAddress, Prefix


class LinkFirewallToAddress(Script):
	class Meta:
		name = "Liaison Firewall-Adresses"
		description = "Permet de lier les Firewall à leurs adresses"

	def run(self, data, commit):
		devicerole=DeviceRole.objects.filter(name="Firewall")[0]
		firewalls=Device.objects.filter(role=devicerole.id)
		for firewall in firewalls:
			if firewall.name == "ANA-FW01":
				site=firewall.site
				prefixes=Prefix.objects.filter(site=site)
				for prefix in prefixes:
					self.log_success(f"prefix found for site {site}: {prefix.prefix}")
