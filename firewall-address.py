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
				self.log_success(f"Currently active on prefix: {prefix}")
				lastIpInPrefix=(prefix.prefix.broadcast-1).format()+"/"+str(prefix.mask_length)
				check_exist=ipam.IPAddress.objects.filter(address=lastIpInPrefix)
				if len(check_exist) == 0:
					lastIpInPrefix=ipam.IPAddress(address=lastIpInPrefix, status="active", dns_name=firewall.name, description=firewall.device_type.model)
					lastIpInPrefix.full_clean()
					lastIpInPrefix.save()
				else:
					lastIpInPrefix=check_exist[0]
				if "PRIV-" in prefix.vlan.group.name:
					if prefix.vlan.group.name == "PRIV-MGMT":
						preLastIpInPrefix=(prefix.prefix.broadcast-2).format()+"/"+str(prefix.mask_length)
						check_exist=ipam.IPAddress.objects.filter(address=preLastIpInPrefix)
						if len(check_exist) == 0:
							preLastIpInPrefix=ipam.IPAddress(address=preLastIpInPrefix, status="active", dns_name=firewall.name+"-oob", description=firewall.device_type.model)
							preLastIpInPrefix.full_clean()
							preLastIpInPrefix.save()
						else:
							preLastIpInPrefix=check_exist[0]
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
