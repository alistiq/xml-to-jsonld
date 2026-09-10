<?xml version="1.0" encoding="UTF-8"?>
<!--
  example.xslt — maps example.xml (synthetic person + address query response)
  to RDF/XML using the CMU (Centrálny model údajov) physical-person and
  location ontologies (pper:, loca:), ready for
  convert_to_jsonld_wContext_nesting.py.
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:msg="http://example.org/example/PersonAddressWS-v1.0.xsd"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:pper="https://data.gov.sk/def/ontology/physical-person/"
    xmlns:loca="https://data.gov.sk/def/ontology/location/"
    xmlns:adms="http://www.w3.org/ns/adms#"
    xmlns:skos="http://www.w3.org/2004/02/skos/core#"
    xmlns:tmid="http://schemas.gov.sk/transform-modul/referencing"
    exclude-result-prefixes="msg tmid">

    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

    <!-- Base URIs for codelists (MetaIS) and for the values resolved against them -->
    <xsl:param name="codelistNs">https://data.gov.sk/set/codelist/</xsl:param>
    <xsl:param name="lau2Ns">https://data.gov.sk/def/lau2/</xsl:param>
    <xsl:param name="unCountryNs">https://data.gov.sk/def/uncountry/</xsl:param>

    <!--
      Fills in a value class (e.g. loca:LAU2, loca:UNCountry) from a tmid:Codelist
      reference: the resolved item's rdf:about IRI, its code as skos:notation, the
      MetaIS codelist it belongs to as skos:inScheme, and its bilingual name as
      skos:prefLabel.
    -->
    <xsl:template name="codelistItem">
        <xsl:param name="element" select="."/>
        <xsl:param name="valueNs"/>
        <xsl:variable name="codelistCode" select="$element/tmid:Codelist/tmid:CodelistCode"/>
        <xsl:variable name="itemCode" select="$element/tmid:Codelist/tmid:CodelistItem/tmid:ItemCode"/>
        <xsl:if test="$itemCode != ''">
            <xsl:attribute name="rdf:about">
                <xsl:value-of select="concat($valueNs, $itemCode)"/>
            </xsl:attribute>
        </xsl:if>
        <skos:notation rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
            <xsl:value-of select="$itemCode"/>
        </skos:notation>
        <xsl:if test="$codelistCode != ''">
            <skos:inScheme rdf:resource="{concat($codelistNs, $codelistCode)}"/>
        </xsl:if>
        <xsl:apply-templates select="$element/tmid:Codelist/tmid:CodelistItem/tmid:ItemName"/>
    </xsl:template>

    <xsl:template match="tmid:CodelistItem/tmid:ItemName">
        <skos:prefLabel xml:lang="{@tmid:lang}">
            <xsl:value-of select="."/>
        </skos:prefLabel>
    </xsl:template>

    <xsl:template match="/">
        <rdf:RDF>
            <xsl:apply-templates select="//msg:Person"/>
        </rdf:RDF>
    </xsl:template>

    <xsl:template match="msg:Person">
        <pper:PhysicalPerson>
            <adms:identifier>
                <adms:Identifier>
                    <skos:notation rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
                        <xsl:value-of select="msg:Identifier"/>
                    </skos:notation>
                </adms:Identifier>
            </adms:identifier>
            <pper:givenName rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
                <xsl:value-of select="msg:GivenName"/>
            </pper:givenName>
            <pper:familyName rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
                <xsl:value-of select="msg:FamilyName"/>
            </pper:familyName>
            <xsl:if test="msg:DateOfBirth">
                <pper:dateOfBirth rdf:datatype="http://www.w3.org/2001/XMLSchema#date">
                    <xsl:value-of select="msg:DateOfBirth"/>
                </pper:dateOfBirth>
            </xsl:if>
            <xsl:if test="msg:Address">
                <pper:permanentResidence>
                    <pper:PermanentResidence>
                        <xsl:apply-templates select="msg:Address"/>
                    </pper:PermanentResidence>
                </pper:permanentResidence>
            </xsl:if>
        </pper:PhysicalPerson>
    </xsl:template>

    <xsl:template match="msg:Address">
        <loca:physicalAddress>
            <loca:PhysicalAddress>
                <xsl:if test="msg:Street">
                    <loca:street>
                        <loca:Street>
                            <skos:prefLabel xml:lang="en">
                                <xsl:value-of select="msg:Street"/>
                            </skos:prefLabel>
                        </loca:Street>
                    </loca:street>
                </xsl:if>
                <xsl:if test="msg:BuildingNumber">
                    <loca:orientationNumber rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
                        <xsl:value-of select="msg:BuildingNumber"/>
                    </loca:orientationNumber>
                </xsl:if>
                <xsl:if test="msg:PostalCode">
                    <loca:postCode>
                        <loca:PostCode>
                            <skos:notation rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
                                <xsl:value-of select="msg:PostalCode"/>
                            </skos:notation>
                        </loca:PostCode>
                    </loca:postCode>
                </xsl:if>
                <xsl:if test="msg:Municipality">
                    <loca:lau2>
                        <loca:LAU2>
                            <xsl:call-template name="codelistItem">
                                <xsl:with-param name="element" select="msg:Municipality"/>
                                <xsl:with-param name="valueNs" select="$lau2Ns"/>
                            </xsl:call-template>
                        </loca:LAU2>
                    </loca:lau2>
                </xsl:if>
                <xsl:if test="msg:Country">
                    <loca:unCountry>
                        <loca:UNCountry>
                            <xsl:call-template name="codelistItem">
                                <xsl:with-param name="element" select="msg:Country"/>
                                <xsl:with-param name="valueNs" select="$unCountryNs"/>
                            </xsl:call-template>
                        </loca:UNCountry>
                    </loca:unCountry>
                </xsl:if>
            </loca:PhysicalAddress>
        </loca:physicalAddress>
    </xsl:template>

</xsl:stylesheet>
