from extras.scripts import *
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site, Region, Manufacturer
from extras.choices import CustomFieldTypeChoices
from ipam.models import VLAN, Prefix, Role, IPAddress
from core.models import ObjectType

class NewSite(Script):

    class Meta:
        name = "Nouveau Site"
        description = "Permet de créer un nouveau site"

    code_site = StringVar(
        description="Code du nouveau site"
    )

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

        # Création de l'objet site avec les données entrées dans l'interface web
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

        self.log_success(f"Created new site: {site}")

        # On récupère le role de l'objet du niveau 3
        # Sur un nouveau site, ça ne peut être qu'un FW
        l3_role = DeviceRole.objects.get(name='Firewall')

        # Création de l'objet firewall avec les données entrées dans l'interface web
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

        ## Création des préfixes pour chaque VLAN

        # Récupération des préfixes dispo sur les plages réservée en /25
        Prefix25Reserved=Prefix.objects.filter(role=Role.objects.get(name="Sites Distants - Infra Cible - 25").id)
        list25AvailablePrefixes = []
        for prefix in Prefix25Reserved:
            availablePrefixes = prefix.get_available_prefixes()
            for availablePrefixList in availablePrefixes.iter_cidrs():
                for availablePrefix in list(availablePrefixList.subnet(25)):
                    list25AvailablePrefixes.append(availablePrefix)

        # On va utilisé le tableau des préfixes dispos, pour ne pas le regénérer tout le temps, 
        # on utilise une variable qui indiquera l'entrée du tableau utilisée
        # cette variable est incrémentée à chaque VLAN
        nb_prefix=0

        # On parcours les VLANs désigné dans l'interface web puis on créé un préfix pour chacun
        # On créé également une adresse IP pour le FW et on l'affecte à une de ses interfaces suivant le cas (PUB, PRIV ou MGMT)
        for vlan in data['vlans_en_25']:

            # Création du préfixe
            vlanNameArray=vlan.name.lower().split('-',1)
            codeSite=data['code_site'].lower()
            prefix=Prefix(
                scope_id=site.id,
                prefix=list25AvailablePrefixes[nb_prefix],
                status='active',
                vlan=vlan,
                scope_type=ObjectType.objects.get(app_label='dcim',model='site'),
                description='lan_'+vlanNameArray[0]+'_'+codeSite+'-'+vlanNameArray[1]
            )
            prefix.full_clean()
            prefix.save()

            # Récupération de la dernière IP du préfixe pour affectation au palo
            lastIpInPrefix=(prefix.prefix.broadcast-1).format()+"/"+str(prefix.mask_length)

            # Création de cette dernière IP
            lastIpInPrefix=IPAddress(address=lastIpInPrefix, status="active", dns_name=firewall.name.replace('-',''), description=firewall.device_type.model)
            lastIpInPrefix.full_clean()
            lastIpInPrefix.save()

            if "PRIV-" in prefix.vlan.group.name:
                # Si on est dans le VLAN PRIV-MGMT, on créé aussi l'avant dernière IP pour le OOB du Palo
                # Sinon on affecte l'adresse IP à ethernet1/7 pour le PRIV
                if prefix.vlan.group.name == "PRIV-MGMT":
                    # Création de l'avant dernière IP
                    preLastIpInPrefix=(prefix.prefix.broadcast-2).format()+"/"+str(prefix.mask_length)
                    preLastIpInPrefix=IPAddress(address=preLastIpInPrefix, status="active", dns_name=firewall.name.replace('-','')+"-oob", description=firewall.device_type.model)
                    preLastIpInPrefix.full_clean()
                    preLastIpInPrefix.save()
                    preLastIpInPrefix.snapshot()
                    firewall.snapshot()
                    # Affectation de l'avant-dernière IP au port management du Firewall et définition de celle-ci comme OOB
                    interface=firewall.interfaces.get(name="management")
                    preLastIpInPrefix.assigned_object = interface
                    preLastIpInPrefix.save()
                    firewall.oob_ip_id = preLastIpInPrefix.id
                    firewall.save()

                    # Affectation de l'adresse IP au port 1/7 du palo
                    interface=firewall.interfaces.get(name="ethernet1/7")
                else:
                    # Si hors du management, on ne fait que l'affectation au port 1/3
                    interface=firewall.interfaces.get(name="ethernet1/3")
            # Si le vlan fait parti du groupe PUB, c'est que l'IP est affectée à l'interface 1/5
            if "PUB-" in prefix.vlan.group.name:
                interface=firewall.interfaces.get(name="ethernet1/5")

            # Liaison de l'IP au firewall
            lastIpInPrefix.assigned_object = interface
            lastIpInPrefix.save()

            # On log la création du préfix pour le VLAN
            self.log_success(f"Create prefix {list25AvailablePrefixes[nb_prefix]} for vlan {vlan}")

            # On incrémente la variable de positionnement dans le tableau
            nb_prefix+=1

        # Récupération des préfixes dispo sur les plages réservée en /23
        Prefix23Reserved=Prefix.objects.filter(role=Role.objects.get(name="Sites Distants - Infra Cible - 23").id)
        list23AvailablePrefixes = []
        for prefix in Prefix23Reserved:
            availablePrefixes = prefix.get_available_prefixes()
            for availablePrefixList in availablePrefixes.iter_cidrs():
                for availablePrefix in list(availablePrefixList.subnet(23)):
                    list23AvailablePrefixes.append(availablePrefix)

        # On va utilisé le tableau des préfixes dispos, pour ne pas le regénérer tout le temps, 
        # on utilise une variable qui indiquera l'entrée du tableau utilisée
        # cette variable est incrémentée à chaque VLAN
        nb_prefix=0

        # On parcours les VLANs désigné dans l'interface web puis on créé un préfix pour chacun
        # On créé également une adresse IP pour le FW et on l'affecte à une de ses interfaces suivant le cas (PUB, PRIV ou MGMT)
        for vlan in data['vlans_en_23']:

            # Création du préfixe
            vlanNameArray=vlan.name.lower().split('-',1)
            codeSite=data['code_site'].lower()
            prefix=Prefix(
                scope_id=site.id,
                prefix=list23AvailablePrefixes[len(list23AvailablePrefixes)-1-nb_prefix],
                status='active',
                vlan=vlan,
                scope_type=ObjectType.objects.get(app_label='dcim',model='site'),
                description='lan_'+vlanNameArray[0]+'_'+codeSite+'-'+vlanNameArray[1]
            )
            prefix.full_clean()
            prefix.save()

            # Récupération de la dernière IP du préfixe pour affectation au palo
            lastIpInPrefix=(prefix.prefix.broadcast-1).format()+"/"+str(prefix.mask_length)

            # Création de cette dernière IP
            lastIpInPrefix=IPAddress(address=lastIpInPrefix, status="active", dns_name=firewall.name.replace('-',''), description=firewall.device_type.model)
            lastIpInPrefix.full_clean()
            lastIpInPrefix.save()

            if "PRIV-" in prefix.vlan.group.name:
                # Si on est dans le VLAN PRIV-MGMT, on créé aussi l'avant dernière IP pour le OOB du Palo
                # Sinon on affecte l'adresse IP à ethernet1/7 pour le PRIV
                if prefix.vlan.group.name == "PRIV-MGMT":
                    # Création de l'avant dernière IP
                    preLastIpInPrefix=(prefix.prefix.broadcast-2).format()+"/"+str(prefix.mask_length)
                    preLastIpInPrefix=IPAddress(address=preLastIpInPrefix, status="active", dns_name=firewall.name.replace('-','')+"-oob", description=firewall.device_type.model)
                    preLastIpInPrefix.full_clean()
                    preLastIpInPrefix.save()
                    preLastIpInPrefix.snapshot()
                    firewall.snapshot()
                    # Affectation de l'avant-dernière IP au port management du Firewall et définition de celle-ci comme OOB
                    interface=firewall.interfaces.get(name="management")
                    preLastIpInPrefix.assigned_object = interface
                    preLastIpInPrefix.save()
                    firewall.oob_ip_id = preLastIpInPrefix.id
                    firewall.save()

                    # Affectation de l'adresse IP au port 1/7 du palo
                    interface=firewall.interfaces.get(name="ethernet1/7")
                else:
                    # Si hors du management, on ne fait que l'affectation au port 1/3
                    interface=firewall.interfaces.get(name="ethernet1/3")
            # Si le vlan fait parti du groupe PUB, c'est que l'IP est affectée à l'interface 1/5
            if "PUB-" in prefix.vlan.group.name:
                interface=firewall.interfaces.get(name="ethernet1/5")

            # Liaison de l'IP au firewall
            lastIpInPrefix.assigned_object = interface
            lastIpInPrefix.save()

            # On log la création du préfix pour le VLAN
            self.log_success(f"Create prefix {list23AvailablePrefixes[len(list23AvailablePrefixes)-1-nb_prefix]} for vlan {vlan}")

            # On incrémente la variable de positionnement dans le tableau
            nb_prefix+=1

class AddVLANToSite(Script):

    class Meta:
        name = "Ajout de VLAN à un site"
        description = "Permet d'ajouter un VLAN à un site sur le nouveau plan d'adressage"

    site = ObjectVar(
        description="Fabricant du device de niveau 3",
        model=Site
    )

    vlans_en_25 = MultiObjectVar(
        description="VLAN avec un subnet en 25",
        model=VLAN,
        required=False
    ).field_attrs.update(queryset=VLAN.objects.all())

    vlans_en_23 = MultiObjectVar(
        description="VLAN avec un subnet en 23",
        model=VLAN,
        required=False
    )

    def run(self, data, commit):

        # Affectation du site à une variable
        site=data['site']
        # Récupération du firewall du site
        firewall=site.devices.get(role=DeviceRole.objects.get(name='Firewall').id)

        # Ajout des prefixes pour les VLANs et affectation au FW

        # Récupération des préfixes dispo sur les plages réservée en /25
        Prefix25Reserved=Prefix.objects.filter(role=Role.objects.get(name="Sites Distants - Infra Cible - 25").id)
        list25AvailablePrefixes = []
        for prefix in Prefix25Reserved:
            availablePrefixes = prefix.get_available_prefixes()
            for availablePrefixList in availablePrefixes.iter_cidrs():
                for availablePrefix in list(availablePrefixList.subnet(25)):
                    list25AvailablePrefixes.append(availablePrefix)

        # On va utilisé le tableau des préfixes dispos, pour ne pas le regénérer tout le temps, 
        # on utilise une variable qui indiquera l'entrée du tableau utilisée
        # cette variable est incrémentée à chaque VLAN
        nb_prefix=0

        # On parcours les VLANs désigné dans l'interface web puis on créé un préfix pour chacun
        # On créé également une adresse IP pour le FW et on l'affecte à une de ses interfaces suivant le cas (PUB, PRIV ou MGMT)
        for vlan in data['vlans_en_25']:

            # Création du préfixe
            vlanNameArray=vlan.name.lower().split('-',1)
            codeSite=site.name.split(' - ')[0].lower()
            prefix=Prefix(
                scope_id=site.id,
                prefix=list25AvailablePrefixes[nb_prefix],
                status='active',
                vlan=vlan,
                scope_type=ObjectType.objects.get(app_label='dcim',model='site'),
                description='lan_'+vlanNameArray[0]+'_'+codeSite+'-'+vlanNameArray[1]
            )
            prefix.full_clean()
            prefix.save()

            # Récupération de la dernière IP du préfixe pour affectation au palo
            lastIpInPrefix=(prefix.prefix.broadcast-1).format()+"/"+str(prefix.mask_length)

            # Création de cette dernière IP
            lastIpInPrefix=IPAddress(address=lastIpInPrefix, status="active", dns_name=firewall.name.replace('-',''), description=firewall.device_type.model)
            lastIpInPrefix.full_clean()
            lastIpInPrefix.save()

            if "PRIV-" in prefix.vlan.group.name:
                # Si on est dans le VLAN PRIV-MGMT, on créé aussi l'avant dernière IP pour le OOB du Palo
                # Sinon on affecte l'adresse IP à ethernet1/7 pour le PRIV
                if prefix.vlan.group.name == "PRIV-MGMT":
                    # Création de l'avant dernière IP
                    preLastIpInPrefix=(prefix.prefix.broadcast-2).format()+"/"+str(prefix.mask_length)
                    preLastIpInPrefix=IPAddress(address=preLastIpInPrefix, status="active", dns_name=firewall.name.replace('-','')+"-oob", description=firewall.device_type.model)
                    preLastIpInPrefix.full_clean()
                    preLastIpInPrefix.save()
                    preLastIpInPrefix.snapshot()
                    firewall.snapshot()
                    # Affectation de l'avant-dernière IP au port management du Firewall et définition de celle-ci comme OOB
                    interface=firewall.interfaces.get(name="management")
                    preLastIpInPrefix.assigned_object = interface
                    preLastIpInPrefix.save()
                    firewall.oob_ip_id = preLastIpInPrefix.id
                    firewall.save()

                    # Affectation de l'adresse IP au port 1/7 du palo
                    interface=firewall.interfaces.get(name="ethernet1/7")
                else:
                    # Si hors du management, on ne fait que l'affectation au port 1/3
                    interface=firewall.interfaces.get(name="ethernet1/3")
            # Si le vlan fait parti du groupe PUB, c'est que l'IP est affectée à l'interface 1/5
            if "PUB-" in prefix.vlan.group.name:
                interface=firewall.interfaces.get(name="ethernet1/5")

            # Liaison de l'IP au firewall
            lastIpInPrefix.assigned_object = interface
            lastIpInPrefix.save()

            # On log la création du préfix pour le VLAN
            self.log_success(f"Create prefix {list25AvailablePrefixes[nb_prefix]} for vlan {vlan}")

            # On incrémente la variable de positionnement dans le tableau
            nb_prefix+=1

        # Récupération des préfixes dispo sur les plages réservée en /23
        Prefix23Reserved=Prefix.objects.filter(role=Role.objects.get(name="Sites Distants - Infra Cible - 23").id)
        list23AvailablePrefixes = []
        for prefix in Prefix23Reserved:
            availablePrefixes = prefix.get_available_prefixes()
            for availablePrefixList in availablePrefixes.iter_cidrs():
                for availablePrefix in list(availablePrefixList.subnet(23)):
                    list23AvailablePrefixes.append(availablePrefix)

        # On va utilisé le tableau des préfixes dispos, pour ne pas le regénérer tout le temps, 
        # on utilise une variable qui indiquera l'entrée du tableau utilisée
        # cette variable est incrémentée à chaque VLAN
        nb_prefix=0

        # On parcours les VLANs désigné dans l'interface web puis on créé un préfix pour chacun
        # On créé également une adresse IP pour le FW et on l'affecte à une de ses interfaces suivant le cas (PUB, PRIV ou MGMT)
        for vlan in data['vlans_en_23']:

            # Création du préfixe
            vlanNameArray=vlan.name.lower().split('-',1)
            codeSite=site.name.split(' - ')[0].lower()
            prefix=Prefix(
                scope_id=site.id,
                prefix=list23AvailablePrefixes[len(list23AvailablePrefixes)-1-nb_prefix],
                status='active',
                vlan=vlan,
                scope_type=ObjectType.objects.get(app_label='dcim',model='site'),
                description='lan_'+vlanNameArray[0]+'_'+codeSite+'-'+vlanNameArray[1]
            )
            prefix.full_clean()
            prefix.save()

            # Récupération de la dernière IP du préfixe pour affectation au palo
            lastIpInPrefix=(prefix.prefix.broadcast-1).format()+"/"+str(prefix.mask_length)

            # Création de cette dernière IP
            lastIpInPrefix=IPAddress(address=lastIpInPrefix, status="active", dns_name=firewall.name.replace('-',''), description=firewall.device_type.model)
            lastIpInPrefix.full_clean()
            lastIpInPrefix.save()

            if "PRIV-" in prefix.vlan.group.name:
                # Si on est dans le VLAN PRIV-MGMT, on créé aussi l'avant dernière IP pour le OOB du Palo
                # Sinon on affecte l'adresse IP à ethernet1/7 pour le PRIV
                if prefix.vlan.group.name == "PRIV-MGMT":
                    # Création de l'avant dernière IP
                    preLastIpInPrefix=(prefix.prefix.broadcast-2).format()+"/"+str(prefix.mask_length)
                    preLastIpInPrefix=IPAddress(address=preLastIpInPrefix, status="active", dns_name=firewall.name.replace('-','')+"-oob", description=firewall.device_type.model)
                    preLastIpInPrefix.full_clean()
                    preLastIpInPrefix.save()
                    preLastIpInPrefix.snapshot()
                    firewall.snapshot()
                    # Affectation de l'avant-dernière IP au port management du Firewall et définition de celle-ci comme OOB
                    interface=firewall.interfaces.get(name="management")
                    preLastIpInPrefix.assigned_object = interface
                    preLastIpInPrefix.save()
                    firewall.oob_ip_id = preLastIpInPrefix.id
                    firewall.save()

                    # Affectation de l'adresse IP au port 1/7 du palo
                    interface=firewall.interfaces.get(name="ethernet1/7")
                else:
                    # Si hors du management, on ne fait que l'affectation au port 1/3
                    interface=firewall.interfaces.get(name="ethernet1/3")
            # Si le vlan fait parti du groupe PUB, c'est que l'IP est affectée à l'interface 1/5
            if "PUB-" in prefix.vlan.group.name:
                interface=firewall.interfaces.get(name="ethernet1/5")

            # Liaison de l'IP au firewall
            lastIpInPrefix.assigned_object = interface
            lastIpInPrefix.save()

            # On log la création du préfix pour le VLAN
            self.log_success(f"Create prefix {list23AvailablePrefixes[len(list23AvailablePrefixes)-1-nb_prefix]} for vlan {vlan}")

            # On incrémente la variable de positionnement dans le tableau
            nb_prefix+=1
    