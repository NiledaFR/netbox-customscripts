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
			site=firewall.site
			prefixes=Prefix.objects.filter(site=site)
			for prefix in prefixes:
				allIps=prefix.get_child_ips()
				lastIpInPrefix=allIps[len(allIps)-1]
				lastIpInPrefix.snapshot()
				if "PRIV-" in prefix.vlan.group.name:
					if prefix.vlan.group.name == "PRIV-MGMT":
						preLastIpInPrefix=allIps[len(allIps)-2]
						preLastIpInPrefix.snapshot()
						firewall.snapshot()
						interface=firewall.interfaces.get(name="management")
						preLastIpInPrefix.assigned_object = interface
						preLastIpInPrefix.save()
						firewall.oob_ip_id = preLastIpInPrefix.id
						firewall.save()
						interface=firewall.interfaces.get(name="ethernet1/7")
					else:
						interface=firewall.interfaces.get(name="ethernet1/3")
				if "PUB-" in prefix.vlan.group.name:
					interface=firewall.interfaces.get(name="ethernet1/5")
				lastIpInPrefix.assigned_object = interface
				lastIpInPrefix.save()
