from extras.scripts import *
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site, Region, Manufacturer
from extras.choices import CustomFieldTypeChoices
from ipam.models import VLAN, Prefix, Role


class NewSite(Script):

    class Meta:
        name = "Nouveau Site"
        description = "Permet de créer un nouveau site"

    code_site = StringVar(
        description="Code du nouveau site",
        required=False
    )

    nom_du_site = StringVar(
        description="Nom du nouveau site",
        required=False
    )

    affectation_du_site = ObjectVar(
        description="Quel type de site?",
        model=Region,
        required=False
    )
    
    adresse_postale = StringVar(
        description="Adresse postale du nouveau site",
        required=False
    )

    type_de_site = ChoiceVar(
        description="Type de site",
        choices=(('OUI','Intermédiaire (avec backbone)'),('NON','Final (sans backbone)')),
        required=False
    )

    type_d_interco = ChoiceVar(
        description="Type d'interco",
        choices=(('ROUTAGE','Routage'),('IPSEC','IPSec'),('L2','L2')),
        required=False
    )

    fabricant_niveau3 = ObjectVar(
        description="Fabricant du device de niveau 3",
        model=Manufacturer,
        required=False
    )
    
    model_niveau3 = ObjectVar(
        description="Modèle du device de niveau 3",
        model=DeviceType,
        query_params={
            'manufacturer_id': '$fabricant_niveau3'
        },
        required=False
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
        if data['code_site'] != "":
            site = Site(
                name=data['code_site']+" - "+data['nom_du_site'],
                slug=slugify(data['nom_du_site']),
                status='active',
                region=data['affectation_du_site'],
                physical_address=data['adresse_postale'],
                custom_field_data=dict(TYPE_DE_SITE=data['type_de_site'],TYPE_INTERCO=data['type_d_interco'])
            )
            site.full_clean()
            site.save()
            typedesite=site.cf.get('TYPE_INTERCO')
            self.log_success(f"Created new site: {site}, avec comme type {typedesite}")

        # Create L3 Equipement
        l3_role = DeviceRole.objects.get(name='Firewall')

        if data['model_niveau3'] != "":
            firewall = Device(
                device_type=data['model_niveau3'],
                name=data['code_site']+"-FW01",
                status='active',
                role=l3_role,
                site=site
            )
            firewall.full_clean()
            firewall.save()
            self.log_success(f"Created firewall: {firewall}")

        # Create Prefixes
        Prefix25Reserved=Prefix.objects.filter(role=Role.objects.get(name="Sites Distants - Infra Cible - 25").id)
        list25AvailablePrefixes = []
        for prefix in Prefix25Reserved:
            availablePrefixes = prefix.get_available_prefixes()
            for availablePrefix in availablePrefixes.iter_cidrs():
                list25AvailablePrefixes.append(list(availablePrefix.subnet(25))

        return '\n'.join(list25AvailablePrefixes)
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
