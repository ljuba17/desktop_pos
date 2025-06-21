import requests
import xml.etree.ElementTree as ET
from html import unescape
import json

# Funkcija za dobijanje osnovnih podataka o firmi na osnovu PIB-a
def vrati_proveri_pib_nbs(pib):
    xml_poruka = f"""
    <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" 
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
        xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <SOAP-ENV:Header>
            <AuthenticationHeader xmlns="http://communicationoffice.nbs.rs">
                <UserName>lavkompjuteri</UserName>
                <Password>lav231055</Password>
                <LicenceID>3c6ea969-57f7-4c75-b2a8-576f8eccf578</LicenceID>
            </AuthenticationHeader>
        </SOAP-ENV:Header>
        <SOAP-ENV:Body>
            <GetCompany xmlns="http://communicationoffice.nbs.rs" 
                SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/iso8859-1">
                <taxIdentificationNumber xsi:type="xsd:int">{pib}</taxIdentificationNumber>
            </GetCompany>
        </SOAP-ENV:Body>
    </SOAP-ENV:Envelope>
    """
    
    headers = {'Content-Type': 'text/xml; charset=utf-8'}
    
    try:
        response = requests.post(
            "https://webservices.nbs.rs/CommunicationOfficeService1_0/CoreXmlService.asmx",
            data=xml_poruka,
            headers=headers,
            verify=False
        )
        response.raise_for_status()
        #print("API Response: ", response.content)  # Dodato za proveru odgovora
    except requests.exceptions.RequestException as e:
        #print("Greška pri slanju zahteva:", e)
        return None

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            namespace = '{http://communicationoffice.nbs.rs}'
            result_text = root.find(f'.//{namespace}GetCompanyResult').text
            
            if result_text:
                inner_xml = unescape(result_text)
                inner_root = ET.fromstring(inner_xml)
                
                # Ekstraktujemo podatke iz odgovora
                naziv = inner_root.find('.//ShortName').text if inner_root.find('.//ShortName') is not None else ""
                mesto = inner_root.find('.//City').text if inner_root.find('.//City') is not None else ""
                pobro = inner_root.find('.//PostalCode').text if inner_root.find('.//PostalCode') is not None else ""
                adresa = inner_root.find('.//Address').text if inner_root.find('.//Address') is not None else ""
                matbr = inner_root.find('.//NationalIdentificationNumber').text if inner_root.find('.//NationalIdentificationNumber') is not None else ""
                naziv1 = inner_root.find('.//Name').text if inner_root.find('.//Name') is not None else ""

                #print("Podaci iz NBS:", naziv, mesto, pobro, adresa, matbr, naziv1)

                # Vrati podatke čak i ako neka polja nisu prisutna
                return naziv, mesto, pobro, adresa, matbr, naziv1
            else:
                #print("Nepotpuni podaci iz NBS.")
                return None

        except ET.ParseError:
            #print("Greška u parsiranju XML-a.")
            return None
    else:
        #print("Greška:", response.status_code)
        return None


# Funkcija za dobijanje tekućih računa firme na osnovu PIB-a
def vrati_pib_tekrac_nbs(ip_pib):
    xml_poruka = f"""
    <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" 
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
        xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <SOAP-ENV:Header>
            <AuthenticationHeader xmlns="http://communicationoffice.nbs.rs">
                <UserName>lavkompjuteri</UserName>
                <Password>lav231055</Password>
                <LicenceID>3c6ea969-57f7-4c75-b2a8-576f8eccf578</LicenceID>
            </AuthenticationHeader>
        </SOAP-ENV:Header>
        <SOAP-ENV:Body>
            <GetCompanyAccount xmlns="http://communicationoffice.nbs.rs" 
                SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                <taxIdentificationNumber xsi:type="xsd:int">{ip_pib}</taxIdentificationNumber>
            </GetCompanyAccount>
        </SOAP-ENV:Body>
    </SOAP-ENV:Envelope>
    """
    
    headers = {'Content-Type': 'text/xml; charset=utf-8'}
    
    try:
        response = requests.post(
            "https://webservices.nbs.rs/CommunicationOfficeService1_0/CompanyAccountXmlService.asmx",
            data=xml_poruka,
            headers=headers,
            verify=False
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        #print("Greška pri slanju zahteva:", e)
        return None

    # Logovanje XML odgovora
    #print("Sadržaj odgovora (RAW XML):", response.text)

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            namespace = '{http://communicationoffice.nbs.rs}'
            result = root.find(f'.//{namespace}GetCompanyAccountResult')
            
            if result is not None and result.text:
                # Dekodira unutrašnji XML
                racuni_xml = unescape(result.text)
                #print("Unutrašnji XML za račune:", racuni_xml)

                racuni_root = ET.fromstring(racuni_xml)
                racuni_list = []
                
                for account in racuni_root.findall('.//CompanyAccount'):
                    bank_code = account.find('BankCode').text
                    acc_number = account.find('AccountNumber').text
                    control_number = account.find('ControlNumber').text
                    bank_name = account.find('BankName').text if account.find('BankName') is not None else "Nepoznato"
                    
                    if bank_code and acc_number and control_number:
                        racuni_list.append({
                            "bank_code": bank_code,
                            "tekuci_racun": f"{bank_code}-{acc_number}-{control_number}",
                            "account_number": acc_number,
                            "control_number": control_number,
                            "bank_name": bank_name  # Dodajemo ime banke
                        })
                    else:
                        print(f"Nedostaju podaci za račun: {bank_code}, {acc_number}, {control_number}")

                if racuni_list:
                    racuni_json_string = json.dumps(racuni_list)
                    return racuni_json_string
                else:
                    #print("Računi nisu pravilno dohvaćeni ili su prazni.")
                    return None
            else:
                #print("Podaci o računima nisu pronađeni ili su prazni.")
                return None
        
        except ET.ParseError:
            #print("Greška u parsiranju unutrašnjeg XML-a.")
            return None
    else:
        #print("Greška prilikom preuzimanja računa:", response.status_code)
        return None