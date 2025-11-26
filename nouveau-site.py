from extras.scripts import *
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site, Region, Manufacturer
from extras.choices import CustomFieldTypeChoices
from ipam.models import VLAN


class NewSite(Script):

    class Meta:
        name = "Nouveau Site"
        description = "Permet de créer un nouveau site"

    nom_du_site = StringVar(
        description="Nom du nouveau site"
    )

    affectation_du_site = ObjectVar(
        description="Quel type de site?",
        model=Region
    )
    
    adresse_postale = StringVar(
        description="Adresse postale du nouveau site"
    )

    type_de_site = ChoiceVar(
        description="Type de site",
        choices=(('OUI','Intermédiaire (avec backbone)'),('NON','Final (sans backbone)'))
    )

    type_d_interco = ChoiceVar(
        description="Type d'interco",
        choices=(('ROUTAGE','Routage'),('IPSEC','IPSec'),('L2','L2'))
    )

    fabricant_niveau3 = ObjectVar(
        description="Fabricant du device de niveau 3",
        model=Manufacturer
    )
    
    model_niveau3 = ObjectVar(
        description="Modèle du device de niveau 3",
        model=DeviceType,
        query_params={
            'manufacturer_id': '$fabricant_niveau3'
        }
    )

    vlans_en_25 = MultiObjectVar(
        description="VLAN avec un subnet en 25",
        model=VLAN,
        required=False
    )

    vlans_en_23 = MultiObjectVar(
        description="VLAN avec un subnet en 23",
        model=VLAN,
        required=False
    )

    def run(self, data, commit):

        # Create the new site
        site = Site(
            name=data['nom_du_site'],
            slug=slugify(data['nom_du_site']),
            status='active',
            region=data['affectation_du_site'],
            physical_address=data['adresse_postale'],
            cf_TYPE_DE_SITE=data['type_de_site'],
            cf_TYPE_INTERCO=data['type_d_interco']
        )
        site.save()
        self.log_success(f"Created new site: {site}")

        # # Create access switches
        # switch_role = DeviceRole.objects.get(name='Access Switch')
        # for i in range(1, data['switch_count'] + 1):
        #     switch = Device(
        #         device_type=data['switch_model'],
        #         name=f'{site.slug.upper()}-SW-{i}',
        #         site=site,
        #         status=DeviceStatusChoices.STATUS_PLANNED,
        #         role=switch_role
        #     )
        #     switch.save()
        #     self.log_success(f"Created new switch: {switch}")

        # # Create routers
        # router_role = DeviceRole.objects.get(name='WAN Router')
        # for i in range(1, data['router_count'] + 1):
        #     router = Device(
        #         device_type=data['router_model'],
        #         name=f'{site.slug.upper()}-RTR-{i}',
        #         site=site,
        #         status=DeviceStatusChoices.STATUS_PLANNED,
        #         role=router_role
        #     )
        #     router.save()
        #     self.log_success(f"Created new router: {router}")

        # # Create APs
        # ap_role = DeviceRole.objects.get(name='Wireless AP')
        # for i in range(1, data['ap_count'] + 1):
        #     ap = Device(
        #         device_type=data['ap_model'],
        #         name=f'{site.slug.upper()}-AP-{i}',
        #         site=site,
        #         status=DeviceStatusChoices.STATUS_PLANNED,
        #         role=ap_role
        #     )
        #     ap.save()
        #     self.log_success(f"Created new AP: {router}")
        
        # # Create Servers
        # server_role = DeviceRole.objects.get(name='vSphere')
        # for i in range(1, data['server_count'] + 1):
        #     server = Device(
        #         device_type=data['server_model'],
        #         name=f'{site.slug.upper()}-VSP-{i}',
        #         site=site,
        #         status=DeviceStatusChoices.STATUS_PLANNED,
        #         role=server_role
        #     )
        #     server.save()
        #     self.log_success(f"Created new server: {router}")

        # # Generate a CSV table of new devices
        # output = [
        #     'name,make,model'
        # ]
        # for device in Device.objects.filter(site=site):
        #     attrs = [
        #         device.name,
        #         device.device_type.manufacturer.name,
        #         device.device_type.model
        #     ]
        #     output.append(','.join(attrs))

        # return '\n'.join(output)
