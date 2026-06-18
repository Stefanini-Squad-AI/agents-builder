      *------------------------------------------------------------*      VRS115
      *  COMPILACAO: SOS 13.6, INCLUINDO COMANDO NO FINAL DO JOB:         VRS115
      *//COBOL.SYSLIB DD DSN=DSA.GESIP7.VP265CPY,DISP=SHR                 VRS115
      *------------------------------------------------------------*      VRS115
       IDENTIFICATION DIVISION.
      *------------------------------------------------------------*      VRS115
       PROGRAM-ID.    VIPP0007.
      *--------------------------------------------------------------*    VRS115
      * COBOL / SQL                   - ATUALIZAR CTE VRS NA WORKING *    VRS115
      *--------------------------------------------------------------*    VRS115
      * PROGRAMA....: VIPP0007 (COBOL II - DB2)                           VRS115
      *                                                                   VRS115
      * DESCRICAO...: SELECAO E CALCULO DE ANUIDADE CARTAO DE CREDITO.    VRS115
      *                                                                   VRS115
      * OBSERVACAO..: NOS DIAS DE CICLO, SELECIONA E CALCULA ANUIDADE     VRS115
      *               PARA OS PORTADORES DAQUELA CARTEIRA.                VRS115
      *               ATUALIZA A TABELA DE PORTADORES (PORT_CRT) E A DE   VRS115
      *               MOVIMENTO (MVT_PND_CT_CRT) COM ANUIDADE CALCULADA.  VRS115
      *               DAH RETURN-CODE '0000' PARA PROCESSAMENTO NORMAL    VRS115
      *               EM DIA DE CICLO E '9000' PARA PROCESSAMENTO NORMAL  VRS115
      *               EM DIA QUE NAO PROCESSAR POR NAO SER CICLO.         VRS115
      *                                                                   VRS115
      * VERSAO......: 001                                                 VRS115
      *                                                                   VRS115
      * ESPECIFICACAO...: CESAR BRANDAO   DATA : 26/05/1999               VRS115
      *                                                                   VRS115
      * PROGRAMACAO.....: FABIO PIRES     DATA : 26/05/1999               VRS115
      *                                                                   VRS115

       AUTHOR.        FABIO_PIRES.

      *----------------------------------------------------------------*  VRS115
       ENVIRONMENT DIVISION.
      *----------------------------------------------------------------*  VRS115

       CONFIGURATION   SECTION.
       SPECIAL-NAMES.
                       DECIMAL-POINT IS COMMA.
       INPUT-OUTPUT    SECTION.

       FILE-CONTROL.
           SELECT  VIPF904E  ASSIGN  TO  UT-S-VIPF904E.
           SELECT  VIPFERRO  ASSIGN  TO  UT-S-VIPFERRO.
           SELECT  VIPFCANU  ASSIGN  TO  UT-S-VIPFCANU.
           SELECT  VIPFSANU  ASSIGN  TO  UT-S-VIPFSANU.
           SELECT  VIPF007S  ASSIGN  TO  UT-S-VIPF007S.
           SELECT  VIPFANUD  ASSIGN  TO  UT-S-VIPFANUD.

      *----------------------------------------------------------------*  VRS115
       DATA DIVISION.
      *----------------------------------------------------------------*  VRS115
      *--------------                                                     VRS115
       FILE SECTION.
      *--------------                                                     VRS115
      *                                                                   VRS115
       FD  VIPF904E
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  290  CHARACTERS                              VRS119
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
       01  FD-REG-VIPF904E             PIC  X(290).                       VRS119
      *                                                                   VRS115
       FD  VIPFERRO
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  80   CHARACTERS
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
       01  FD-REG-VIPFERRO             PIC  X(80).
      *                                                                   VRS115
       FD  VIPFCANU
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  100  CHARACTERS                              VRS128
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
       01  FD-REG-VIPFCANU             PIC  X(100).                       VRS128
      *                                                                   VRS115
       FD  VIPFSANU
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  30   CHARACTERS
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
       01  FD-REG-VIPFSANU             PIC  X(30).
      *                                                                   VRS115
       FD  VIPFANUD
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  100   CHARACTERS
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
       01  FD-REG-VIPFANUD             PIC  X(100).
      *                                                                   VRS115
       FD  VIPF007S
           BLOCK   CONTAINS  0    RECORDS
           RECORD  CONTAINS  29   CHARACTERS
           RECORDING   MODE  F
           LABEL     RECORD  STANDARD.
      *                                                                   VRS115
       01  FD-REG-VIPF007.
           10 F007-TIP-REG              PIC  X(001).
           10 F007-NR-CT-CRT            PIC S9(009) COMP.
           10 F007-NR-SEQL-TITD-PORT    PIC S9(004) COMP.
           10 F007-VL-ANUD-CBR          PIC S9(009)V9(2) COMP-3.
           10 F007-VL-DSC-ANUD          PIC S9(009)V9(2) COMP-3.
           10 F007-DT-MVT-ANUD          PIC  X(010).
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
       WORKING-STORAGE                 SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
       77  CTE-INICIO-WSS              PIC  X(034)    VALUE
               '*** VIPP0007 WSS COMECA AQUI ***'.
       77  CTE-FINAL                   PIC  X(016)    VALUE
               '999 - FIM NORMAL'.
       77  CTE-PROG                    PIC  X(017)    VALUE
               '*** VIPP0007 ***'.
       77  CTE-VERS                    PIC  X(006)    VALUE 'VRS136'.
      *
101219 77  VIPP0078                    PIC  X(008)    VALUE 'VIPP0078'.   VRS115
101219 77  VIPP078A                    PIC  X(008)    VALUE 'VIPP078A'.   VRS115
101219 77  VIPP0082                    PIC  X(008)    VALUE 'VIPP0082'.   VRS115
101219 77  VIPSB957                    PIC  X(008)    VALUE 'VIPSB957'.   VRS115
101219 77  VIPSB958                    PIC  X(008)    VALUE 'VIPSB958'.   VRS115
101219 77  VIPST752                    PIC  X(008)    VALUE 'VIPST752'.   VRS115
101219 77  VIPP4848                    PIC  X(008)    VALUE 'VIPP4848'.   VRS115
       77  VIPP4865                    PIC  X(008)    VALUE 'VIPP4865'.   VRS122
       77  VIPST05V                    PIC  X(008)    VALUE 'VIPST05V'.   VRS122
101219 77  VIPP4854                    PIC  X(008)    VALUE 'VIPP4854'.   VRS115
      *
101219 77  SBVERSAO                    PIC  X(008)    VALUE 'SBVERSAO'.   VRS115
101219 77  SBCURDAT                    PIC  X(008)    VALUE 'SBCURDAT'.   VRS115
101219 77  SBABEND                     PIC  X(008)    VALUE 'SBABEND'.    VRS115
101219 77  SBDATA                      PIC  X(008)    VALUE 'SBDATA'.     VRS115
       77  SBCPU                       PIC  X(008)    VALUE 'SBCPU'.      VRS133
       77  NOME-CPU                    PIC  X(004)    VALUE SPACES.       VRS133
       77  GDA-MOCK                    PIC  9(004)    VALUE 0.
      *
       77  DO-TAB                      PIC S9(005)    VALUE +0 COMP-3.
       77  GDA-CTRL                    PIC  9(001)    VALUE 0.
       77  AUX-NR-CT-CRT               PIC S9(009)    COMP VALUE 1.
       77  GDA-CD-ANUD-PDAO            PIC S9(009)    COMP.
       77  GDA-CD-ANUD-PDAO-I2         PIC S9(004)    COMP.
       77  GDA-VL-ANUD-CBR-PORT        PIC S9(011)V99 COMP-3.
       77  GDA-VL-DSC-PORT             PIC S9(011)V99 COMP-3.
       77  GDA-CONTROL                 PIC  X(001)    VALUE SPACES.
       77  GDA-RETORNO                 PIC  X(001)    VALUE SPACES.
       77  GDA-CNT                     PIC  9(001)    VALUE 1.
       77  CNT-REG-VIPF007             PIC  9(007)    VALUE 0.
       77  CNT-PORT-INV-ATDG           PIC  9(007)    VALUE 0.
       77  CNT-PORT-INV-N-ATDG         PIC  9(007)    VALUE 0.
       77  CNT-ERRO-DB2                PIC  9(005)    VALUE 0.
       77  GDA-CONTAS-ATU              PIC  X(057)    VALUE SPACES.
       77  GDA-CD-TIP-CBR-ANUD         PIC S9(004)    VALUE 0 COMP.
       77  GDA-IN-CBR-ANUD             PIC  X(001)    VALUE SPACE.
       77  GDA-NR-SEQL-FAT-CT-CRT      PIC S9(009)    VALUE 0 COMP.
       77  GDA-VL-SDO-FAT-CT-CRT       PIC S9(017)    VALUE 0 COMP-3.
       77  GDA-TP-VNCT                 PIC S9(004)    VALUE 0 COMP.
      *77  GDA-CD-CLDR                 PIC S9(009)    VALUE 0 COMP.       VRS115
       77  GDA-DIA-VENCIMENTO          PIC S9(004)    VALUE 0 COMP.
       77  GDA-SDO-CONTA               PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-PCL-TIT              PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-PCL-ADC              PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-QT-PCL-TIT              PIC S9(004)    VALUE 0 COMP.
       77  GDA-QT-PCL-ADC              PIC S9(004)    VALUE 0 COMP.
       77  GDA-QT-PCL-TIT-DB2          PIC S9(004)    VALUE 0 COMP.
       77  GDA-QT-PCL-ADC-DB2          PIC S9(004)    VALUE 0 COMP.
       77  GDA-QT-PCL-PDAO             PIC S9(004)    VALUE 0 COMP.
       77  GDA-NR-SEQL                 PIC S9(004)    VALUE 0 COMP.
       77  GDA-QT-AA-VLD               PIC S9(004)    VALUE 0 COMP.
       77  GDA-CD-ANUD                 PIC S9(004)    VALUE 0 COMP.
       77  GDA-VL-ANUD                 PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-PRAT                 PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-ESTN-DAA             PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-QTPA                    PIC  9(002)    VALUE 0.
       77  GDA-PARCELA                 PIC S9(004)    VALUE 0 COMP.
       77  GDA-CD-TIP-RST-PLST         PIC S9(004)    VALUE 0 COMP.
       77  GDA-REG-GRAV-ANUD           PIC  9(009)    VALUE 0.
       77  GDA-REG-DSC-ENCT            PIC  9(009)    VALUE 0.            VRS120
       77  MSK-REG-DSC-ENCT            PIC ZZZ.ZZZ.ZZ9.                   VRS120
       77  INULL-DT-EFT                PIC S9(004)    VALUE 0 COMP.
       77  INULL-SEQL                  PIC S9(004)    VALUE 0 COMP.
       77  INULL-VL-TIP-DT             PIC S9(004)    VALUE 0 COMP.
       77  INULL-QT-DCML               PIC S9(004)    VALUE 0 COMP.
       77  INULL-DESC-MAX              PIC S9(004)    VALUE 0 COMP.
       77  INULL-DESC-SUM              PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL-CD-MDU       PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL-NR-PRIO      PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL-VLD-AN       PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL-CAR-AN       PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL-NVL-ACSS     PIC S9(004)    VALUE 0 COMP.
       77  WS-BB-NOT-NULL              PIC S9(004)    VALUE 0 COMP.
       77  GDA-IND-RATF                PIC  X(001)    VALUE SPACE.
       77  GDA-IND-RATD                PIC  X(001)    VALUE SPACE.
       77  GDA-INDICADOR-CBR           PIC S9(004)    VALUE 0 COMP.
       77  GDA-IN-CBR                  PIC  X(001)    VALUE SPACE.
       77  GDA-TIT-NAO-ATIVADO         PIC  X(001)    VALUE SPACE.
       77  GDA-COUNT-CRT               PIC S9(017)    VALUE 0 COMP-3.
       77  GDA-PERC-DESC               PIC  9(009)    VALUE 0.
       77  GDA-PERC                    PIC  9(009)    VALUE 0.
       77  GDA-PERC-ANUD               PIC  9(002)V99 VALUE 0.
       77  GDA-CTRL-CICLO              PIC  9(001)    VALUE 0.
       77  GDA-IDENT-DSC               PIC  X(001)    VALUE SPACES.
       77  GDA-TIPO                    PIC  X(003)    VALUE SPACES.
       77  GDA-VL-MCI                  PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-CTRA                 PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-INV                  PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-904                  PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-4865                 PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-VL-4848                 PIC S9(011)V99 VALUE 0 COMP-3.
       77  GDA-MAIOR                   PIC S9(007)V99 VALUE 0 COMP-3.
       77  IND-DSC-SUB                 PIC  X(001)    VALUE SPACES.
       77  IND-DSC-OCI                 PIC  X(001)    VALUE 'N'.
       77  IND-EH-MES                  PIC  9(002)    VALUE 0.
           88 EH-MES-31                VALUE 01 03 05 07 08 10 12.
           88 EH-MES-30                VALUE 04 06 09 11.
      *                                                                   VRS115
       77  WS-GRUPO-MDLD               PIC  9    VALUE 0.
           88 MODALIDADE-PRIVATE       VALUE  1.
           88 NAO-PRIVATE              VALUE  2.
      *                                                                   VRS115
       77  WS-GRUPO-MDNAC              PIC  9    VALUE 0.
           88 NACIONAL                 VALUE  1.
           88 DIFERENCIADA             VALUE  2.
      *                                                                   VRS115
       77  DIVI                        PIC  9(009)    VALUE 0.
       77  RESTO                       PIC  9(009)    VALUE 0.
       77  WCOUNT                      PIC S9(009)    VALUE 0 COMP-3.
       77  WCOUNT2                     PIC S9(009)    VALUE 0 COMP-3.
       77  WIND-DESC                   PIC  9(002)    VALUE 0.
       77  WIND-GRMDLD                 PIC  9(002)    VALUE 0.
       77  WIND-FIM                    PIC  9(002)    VALUE 0.
       77  WIND-FIM-GRMDLD             PIC  9(002)    VALUE 0.
       77  FIM-VIPF904                 PIC  9(001)    VALUE 0.
       77  WPRORAT-DIF-DATAS           PIC  9(004)    VALUE 0.
       77  WPRORAT-QT-ADC              PIC  9(004)    VALUE 0.
       77  WPRORAT-VL-ADC              PIC  9(011)V99 VALUE 0.
       77  WDESCRICAO                  PIC  X(040)    VALUE SPACE.
       77  WPARC-PEND                  PIC  9(002)    VALUE 0.
       77  WPARC-TOTAL                 PIC  9(002)    VALUE 0.
       77  WCOMMIT                     PIC  9(005)    VALUE 0.
       77  WGRAVADOS                   PIC  9(006)    VALUE 0.
       77  WCONTROL-CICLO              PIC  9(002)    VALUE 0.
       77  WPONTO-RESTART              PIC  9(017)    VALUE 0 COMP-3.
       77  WCONTROL-LEITURA            PIC  X(001)    VALUE SPACES.
       77  WDESCONTO-OCI               PIC  9(002)V99 VALUE 0.
       77  WS-PRORATA                  PIC  X(001)    VALUE SPACES.
       77  WS-NR-CT-CRT                PIC  9(009)    VALUE 0.
       77  PRIMEIRA-VEZ                PIC  9(001)    VALUE 0.

       77  WRK-CD-ANUD-CVN             PIC S9(004)    VALUE 0 COMP.
       77  WRK-IN-CBR-PRO-RATD         PIC X(1)       VALUE SPACES.
       77  WRK-IN-CBR-APVC-DEB         PIC X(1)       VALUE SPACES.
       77  WRK-DT-INC-VGC              PIC X(10)      VALUE SPACES.
       77  WRK-DT-FIM-VGC              PIC X(10)      VALUE SPACES.
       77  WRK-VL-PCL-TIT              PIC S9(9)V9(2) VALUE 0 COMP-3.
       77  WRK-VL-PCL-ADC              PIC S9(9)V9(2) VALUE 0 COMP-3.
       77  WRK-QT-PCL-TIT              PIC S9(4)      VALUE 0 COMP.
       77  WRK-QT-PCL-ADC              PIC S9(4)      VALUE 0 COMP.
       77  WRK-TX-ANUD                 PIC X(70)      VALUE SPACES.
       77  WRK-CD-MDU-LGC              PIC S9(4)      VALUE 0 COMP.
       77  WRK-NR-PRIO-ANUD-CVN        PIC S9(4)      VALUE 0 COMP.
       77  WRK-QT-AA-VLD-ANUD          PIC S9(4)      VALUE 0 COMP.
       77  WRK-QT-AA-CARE-ANUD         PIC S9(4)      VALUE 0 COMP.
       77  WRK-CD-NVL-ACSS             PIC S9(4)      VALUE 0 COMP.
       77  DESC-ANUID                  PIC X(12) VALUE SPACES.
       77  GDA-SEQL-REFNUM             PIC 9(09) VALUE ZEROS.
       77  GDA-SUB-MDLD                PIC S9(04) COMP.

       01  VIPKERRO.
           03 VIPKERRO-NR-CRT          PIC  9(09)     VALUE ZEROS.
           03 VIPKERRO-SEQ-TIT         PIC  9(04)     VALUE ZEROS.
           03 VIPKERRO-MSG-ERRO        PIC  X(60)     VALUE SPACES.

       01  VIPKCONF.
           03 VIPKCONF-NR-CRT          PIC  9(09)     VALUE ZEROS.
           03 VIPKCONF-SEQ-TIT         PIC  9(04)     VALUE ZEROS.
           03 VIPKCONF-DT-PRI-COMPRA   PIC  9(08)     VALUE ZEROS.
           03 VIPKCONF-CD-CLI            PIC S9(009) COMP VALUE 0.        VRS128
           03 VIPKCONF-CD-MDLD-CRT       PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-CD-TITD-PORT      PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-CD-TIP-CBR-ANUD   PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-IN-CBR-ANUD       PIC  X(001)      VALUE ' '.      VRS128
           03 VIPKCONF-DT-PRX-ANIV-ANUD  PIC  X(010)      VALUE ' '.      VRS128
           03 VIPKCONF-DT-PRMO-CBR-ANUD  PIC  X(010)      VALUE ' '.      VRS128
           03 VIPKCONF-DT-INC-CBR-ANUD   PIC  X(010)      VALUE ' '.      VRS128
           03 VIPKCONF-NR-PCL-PND-ANUD   PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-VL-PCL-ANUD       PIC S9(011)V99 COMP-3 VALUE 0.   VRS128
           03 VIPKCONF-QT-TTL-PCL-ANUD   PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-CD-SUB-MDLD-CRT   PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-CD-ANUD-LIDO      PIC S9(004) COMP VALUE 0.        VRS128
           03 VIPKCONF-VL-ANUD-FATD      PIC S9(011)V99 COMP-3 VALUE 0.   VRS128
           03 FILLER                     PIC  X(016)      VALUE ' '.      VRS128

       01  VIPKANUD.
           03 VIPKANUD-NR-CT-CRT       PIC S9(009)    COMP.
           03 VIPKANUD-CD-MDLD-CRT     PIC S9(004)    COMP.
           03 VIPKANUD-NR-PLST         PIC S9(017)    COMP-3.
           03 VIPKANUD-DATA-ATUAL      PIC  X(010)    VALUE SPACE.
           03 VIPKANUD-DESCRICAO       PIC  X(040)    VALUE SPACE.
           03 VIPKANUD-CD-TRAN         PIC S9(07)     USAGE COMP-3.
           03 VIPKANUD-VL-PCL-ANUD     PIC S9(011)V99 COMP-3.
      *    03 FILLER                   PIC  X(21).                        VRS128
           03 VIPKANUD-CD-CLIENTE      PIC S9(09)     COMP.               VRS128
           03 VIPKANUD-NR-SEQL-TITD    PIC S9(004)    COMP.               VRS128
           03 FILLER                   PIC  X(18).                        VRS128
       01  FILLER REDEFINES VIPKANUD.
           03 VIPKANUD-DAA             PIC  X(03).
           03 VIPKANUD-NR-CT-CRT-DAA   PIC S9(009)    COMP.
           03 VIPKANUD-NR-SEQL-TITD-DAA PIC S9(004)    COMP.
           03 VIPKANUD-CD-MDLD-CRT-DAA PIC S9(004)    COMP.
           03 VIPKANUD-CD-SUBMDLD-DAA  PIC S9(004)    COMP.
           03 VIPKANUD-NR-PLST-DAA     PIC S9(017)    COMP-3.
           03 VIPKANUD-DATA-ATUAL-DAA  PIC  X(010).
           03 VIPKANUD-CD-CLIENTE-DAA  PIC S9(09)     COMP.
           03 VIPKANUD-VL-PCL-ANUD-DAA PIC S9(011)V99 COMP-3.
           03 VIPKANUD-VL-DSC-ANUD-DAA PIC S9(011)V99 COMP-3.
           03 VIPKANUD-VL-DSC-904      PIC S9(009)V99 COMP-3.
           03 VIPKANUD-VL-DSC-MCI      PIC S9(009)V99 COMP-3.
           03 VIPKANUD-VL-DSC-CTRA     PIC S9(009)V99 COMP-3.
           03 VIPKANUD-VL-DSC-INV      PIC S9(009)V99 COMP-3.
           03 VIPKANUD-VL-DSC-4865     PIC S9(009)V99 COMP-3.
           03 VIPKANUD-VL-DSC-4848     PIC S9(009)V99 COMP-3.
      *    03 FILLER                   PIC  X(26).                        VRS128
           03 FILLER                   PIC  X(15).                        VRS128

      ******************************************************************  VRS115
      *                      Area da SBCURDAT                          *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01  W-TIPO                      PIC  9(001)    VALUE 2.
       01  W-DATA                      PIC  9(008)    VALUE ZEROS.
       01  W-HORA                      PIC  9(006)    VALUE ZEROS.
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                      Area da SBDATA                            *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01 FUNCAO                       PIC  X(003)    VALUE 'F03'.
       01 ARG01                        PIC  9(008)    VALUE ZEROS.
       01 ARG02                        PIC  9(008)    VALUE ZEROS.
       01 ARG03                        PIC S9(005)    VALUE ZEROS.
      *                                                                   VRS115
       01 FUNCAO-13                    PIC  X(003)    VALUE 'F13'.
       01 ARG01-13                     PIC  9(008)    VALUE ZEROS.
       01 ARG02-13                     PIC  9(008)    VALUE ZEROS.
       01 ARG03-13                     PIC S9(005)    VALUE ZEROS.
       01 ARG03-FORM3  REDEFINES  ARG03-13.
          03 QTD-DIAS-CORR             PIC S9(005).
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                      Areas Auxiliares                          *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01 CONTAS-REG.
          03 CONTAS-CD-CLI             PIC S9(009)    COMP.
          03 CONTAS-NR-CT-CRT          PIC S9(009)    COMP.
          03 CONTAS-CD-MDLD-CRT        PIC S9(004)    COMP.
          03 CONTAS-NR-PLST            PIC S9(017)    COMP-3.
          03 CONTAS-NR-SEQL-FAT-CT-CRT PIC S9(009)    COMP.
          03 CONTAS-CD-TITD-PORT       PIC S9(004)    COMP.
          03 CONTAS-NR-SEQL-TITD-PORT  PIC S9(004)    COMP.
          03 CONTAS-CD-TIP-CBR-ANUD    PIC S9(004)    COMP.
          03 CONTAS-IN-CBR-ANUD        PIC  X(001).
          03 CONTAS-DT-PRX-ANIV-ANUD   PIC  X(010).
          03 CONTAS-CD-ANUD            PIC S9(004)    COMP.
          03 CONTAS-DT-PRMO-CBR-ANUD   PIC  X(010).
          03 CONTAS-DT-INC-CBR-ANUD    PIC  X(010).
          03 CONTAS-NR-PCL-PND-ANUD    PIC S9(004)    COMP.
          03 CONTAS-VL-PCL-ANUD        PIC S9(011)V99 COMP-3.
          03 CONTAS-QT-TTL-PCL-ANUD    PIC S9(004)    COMP.
          03 CONTAS-NR-CT-CRT-ANT      PIC S9(017)    COMP-3.
          03 CONTAS-CD-SUB-MDLD-CRT    PIC S9(004) COMP.
          03 CONTAS-DT-ABTR-CT         PIC  X(010).                       VRS122
          03 CONTAS-CD-ANUD-LIDO       PIC S9(004)    COMP.               VRS128
          03 CONTAS-VL-ANUD-FATD       PIC S9(011)V99 COMP-3.             VRS128
      *                                                                   VRS115
       01 DESCONTO-REG.
          03 DESCONTO-DT-VIGENCIA      PIC  X(010).
          03 DESCONTO-FAIXA            PIC S9(009)    COMP.
          03 DESCONTO-PERCENTUAL       PIC S9(009)    COMP.
          03 DESCONTO-VALOR            PIC S9(009)    COMP.
      *                                                                   VRS115
       01 GRMDLD-REG.
          03 GRMDLD-CD-MDLD-CRT        PIC S9(004)    COMP.
      *                                                                   VRS115
       01 GDA-PARM.
          03 GDA-CTA-PCPL              PIC  9(009).
          03 GDA-IND-DATA              PIC  X(001).
          03 GDA-DT-TRANS              PIC  9(008).
          03 GDA-IND-CTA               PIC  9(001).
          03 GDA-CD-MDLD-CRT-CRD       PIC S9(004) COMP.
          03 GDA-CD-SUB-MDLD-CRT       PIC S9(004) COMP.
          03 GDA-CTA-SEC               PIC  9(009).
          03 GDA-SQL-CODE              PIC S9(004).
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                        Area de Datas                           *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01  GDA-SBC-DATA                PIC  9(008).
       01  FILLER                      REDEFINES  GDA-SBC-DATA.
           03  GDA-SBC-DIA             PIC  9(002).
           03  GDA-SBC-MES             PIC  9(002).
           03  GDA-SBC-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-SBD-DATA                PIC  9(008).
       01  FILLER                      REDEFINES  GDA-SBD-DATA.
           03  GDA-SBD-DIA             PIC  9(002).
           03  GDA-SBD-MES             PIC  9(002).
           03  GDA-SBD-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DATA-ATUAL              PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DATA-ATUAL.
           03  GDA-ATU-DIA             PIC  9(002).
           03  FILLER-ATU1             PIC  X(001).
           03  GDA-ATU-MES             PIC  9(002).
           03  FILLER-ATU2             PIC  X(001).
           03  GDA-ATU-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DATA-FUTURA             PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DATA-FUTURA.
           03  GDA-FUT-DIA             PIC  9(002).
           03  FILLER-FUT1             PIC  X(001).
           03  GDA-FUT-MES             PIC  9(002).
           03  FILLER-FUT2             PIC  X(001).
           03  GDA-FUT-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DTA-ANI-TIT             PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DTA-ANI-TIT.
           03  GDA-ANI-DIA             PIC  9(002).
           03  FILLER-ANI1             PIC  X(001).
           03  GDA-ANI-MES             PIC  9(002).
           03  FILLER-ANI2             PIC  X(001).
           03  GDA-ANI-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DTA-PRIME-CBR-ANUD      PIC  X(010) VALUE '  .  .    '.
       01  FILLER                   REDEFINES  GDA-DTA-PRIME-CBR-ANUD.
           03  GDA-PRIME-DIA           PIC  9(002).
           03  FILLER-PRI1             PIC  X(001).
           03  GDA-PRIME-MES           PIC  9(002).
           03  FILLER-PRI2             PIC  X(001).
           03  GDA-PRIME-ANO           PIC  9(004).
      *                                                                   VRS115
       01  GDA-DTA-INC-CBR-ANUD        PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DTA-INC-CBR-ANUD.
           03  GDA-INC-CBR-ANUD-DIA    PIC  9(002).
           03  FILLER-INC1             PIC  X(001).
           03  GDA-INC-CBR-ANUD-MES    PIC  9(002).
           03  FILLER-INC2             PIC  X(001).
           03  GDA-INC-CBR-ANUD-ANO    PIC  9(004).
      *                                                                   VRS115
       01  GDA-DTA-VENC                PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DTA-VENC.
           03  GDA-VEN-DIA             PIC  9(002).
           03  FILLER-VEN1             PIC  X(001).
           03  GDA-VEN-MES             PIC  9(002).
           03  FILLER-VEN2             PIC  X(001).
           03  GDA-VEN-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DATA-DB2                PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DATA-DB2.
           03  GDA-DB2-DIA             PIC  9(002).
           03  FILLER                  PIC  X(001).
           03  GDA-DB2-MES             PIC  9(002).
           03  FILLER                  PIC  X(001).
           03  GDA-DB2-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DATA-EFETIVA            PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DATA-EFETIVA.
           03  GDA-EFT-DIA             PIC  9(002).
           03  FILLER-EFT1             PIC  X(001).
           03  GDA-EFT-MES             PIC  9(002).
           03  FILLER-EFT2             PIC  X(001).
           03  GDA-EFT-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-AMD-FINAL               PIC  9(008).
       01  FILLER                      REDEFINES  GDA-AMD-FINAL.
           03  GDA-AMD-ANO             PIC  9(004).
           03  FILLER REDEFINES GDA-AMD-ANO.
               05 GDA-SEC              PIC  9(002).
               05 GDA-ANO              PIC  9(002).
           03  GDA-AMD-MES             PIC  9(002).
           03  GDA-AMD-DIA             PIC  9(002).
      *                                                                   VRS115
       01  GDA-DT-INI-CBR               PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DT-INI-CBR.
           03  GDA-DT-INI-CBR-AA       PIC  9(004).
           03  GDA-DT-INI-CBR-MM       PIC  9(002).
           03  GDA-DT-INI-CBR-DD       PIC  9(002).
      *                                                                   VRS115
       01  GDA-DT-FIM-CBR               PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DT-FIM-CBR.
           03  GDA-DT-FIM-CBR-AA       PIC  9(004).
           03  GDA-DT-FIM-CBR-MM       PIC  9(002).
           03  GDA-DT-FIM-CBR-DD       PIC  9(002).
      *                                                                   VRS115
       01  GDA-DT-ATU-N08               PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DT-ATU-N08.
           03  GDA-DT-ATU-N08-AA       PIC  9(004).
           03  GDA-DT-ATU-N08-MM       PIC  9(002).
           03  GDA-DT-ATU-N08-DD       PIC  9(002).
      *                                                                   VRS115
       01  GDA-AMD-TEMP                PIC  9(008).
       01  FILLER                      REDEFINES  GDA-AMD-TEMP.
           03  GDA-AMD-ANO-T           PIC  9(004).
           03  GDA-AMD-MES-T           PIC  9(002).
           03  GDA-AMD-DIA-T           PIC  9(002).
      *                                                                   VRS115
       01  GDA-DATA-VIP7               PIC  X(010) VALUE '  .  .    '.
       01  FILLER                      REDEFINES  GDA-DATA-VIP7.
           03  GDA-VIP-DIA             PIC  9(002).
           03  FILLER-VIP1             PIC  X(001).
           03  GDA-VIP-MES             PIC  9(002).
           03  FILLER-VIP2             PIC  X(001).
           03  GDA-VIP-ANO             PIC  9(004).
      *                                                                   VRS115
       01  GDA-DATA-VIP-INV            PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DATA-VIP-INV.
           03  GDA-VIP-ANO-INV         PIC  9(004).
           03  GDA-VIP-MES-INV         PIC  9(002).
           03  GDA-VIP-DIA-INV         PIC  9(002).
      *                                                                   VRS115
       01  GDA-DATA-FUT-INVER          PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DATA-FUT-INVER.
           03  GDA-INV-ANO             PIC  9(004).
           03  GDA-INV-MES             PIC  9(002).
           03  GDA-INV-DIA             PIC  9(002).
      *                                                                   VRS115
       01  GDA-DATA-ANI-INVER          PIC  9(008).
       01  FILLER                      REDEFINES  GDA-DATA-ANI-INVER.
           03  GDA-ANO-ANI             PIC  9(004).
           03  GDA-MES-ANI             PIC  9(002).
           03  GDA-DIA-ANI             PIC  9(002).
      *                                                                   VRS115
       01  GDA-NR-CT-CRT-ANT           PIC  9(017).
       01  FILLER                      REDEFINES  GDA-NR-CT-CRT-ANT.
           03  FILLER                  PIC  9(001).
           03  GDA-IND-BNC             PIC  9(001).
           03  FILLER                  PIC  9(015).
      *
       01 GDA-DTABTDAA-INV             PIC  X(008).                       VRS122
       01 GDA-DT-ABTR-CT-INV           PIC  X(008).                       VRS122

       01  WS-AREA-CICS.
           03  VIPKCICS                PIC  X(00085)  VALUE   SPACES.

       01  IN-FIM-EXCO                 PIC  X(001)    VALUE 'N'.          VRS121
           88 FIM-EXCO                                VALUE 'S'.          VRS121
      *                                                                   VRS121
      ******************************************************************  VRS121
      *                   Tabela de Grupos de Exceção.                 *  VRS121
      ******************************************************************  VRS121
      *                                                                   VRS121
       01  WIND                        PIC S9(004) COMP-5.                VRS121
       01  GREXCO-CD-MDLD-CRT          PIC S9(004) COMP.                  VRS121
       01  WS-TABELA-GREXCO.                                              VRS121
           02 TAB-GREXCO               OCCURS 100 TIMES.                  VRS121
              03 TAB-CD-MDLD-EXCO      PIC S9(004) COMP.                  VRS121
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                   Books de acesso ao VSAM.                     *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01  LK82-MVT-PARAM.
      *    COPYBOOK TRANSACAO MVT                               ***       VRS115
-INC  VIPK082W
      *    COPYBOOK ANUD                                        ***       VRS115
-INC  VIPK140D
      *    COPYBOOK TABELA CONVENIOS PRIVATE LABEL              ***       VRS115
-INC  VIPK573D
      *   DCLGEN DA TABELA DB2VIP.CT_CRT                        ***       VRS115
-INC  VIPK101D
      *   DCLGEN DA TABELA DB2VIP.PORT_CRT                      ***       VRS115
-INC  VIPK102D
      *   DCLGEN DA TABELA DB2VIP.PLST_PORT                     ***       VRS115
-INC  VIPK103D
      *   DCLGEN DA TABELA DB2VIP.DSC_ANUD_SUB_MDLD             ***       VRS115
-INC  VIPK02LD
      *    COPYBOOK TABELA PARAMETROS PRIVATE LABEL             ***       VRS115
-INC  VIPK585D
      *    COPYBOOK TABELA LIDER                                ***       VRS115
-INC  VIPK207D
      *                                                                   VRS115
       01  WS-VIPKS957.
-INC  VIPKS957

       01  WS-VIPKS958.
-INC  VIPKS958
      *                                                                   VRS115
      *    COPYBOOK DE VIPP4848                                           VRS115
       01  PARM-VIPP4848.
-INC   VIPK048W
      *                                                                   VRS115
      *    COPYBOOK DE VIPP4854                                           VRS115
       01  PARM-VIPP4854.
-INC   VIPK4854
      *    COPYBOOK DE VIPP4865                                           VRS122
       01  PARM-VIPP4865.                                                 VRS122
-INC   VIPK4865                                                           VRS122
      *
      *    COPYBOOK DE VIPKT05V
       01  PARM-VIPST05V.
-INC   VIPKT05V
      *    COPYBOOK DE VIPST752                                           VRS122
       01  PARM-VIPST752.
-INC  VIPKT752
           COPY CCS301.
      *    COPYBOOK ABEND - CARDPAC                             ***       VRS115
           COPY CCS302.
      *    COPYBOOK ERRO SQL                                    ***       VRS115
-INC  DBUK0000

      * Book da Tabela DB2VIP.APL_DSC_AUTC_ANUD
-INC VIPK0A1D
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                   Area para leitura de arquivos                *  VRS115
      ******************************************************************  VRS115
      *----------------------------                                       VRS115
      *  BOOK DO ARQUIVO VIPF904                                          VRS115
      *----------------------------                                       VRS115
-INC  VIPK904G
      *                                                                   VRS115
-INC  VIPK748D

-INC HLPKDFHE
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                   Area de acesso a subrotina                   *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01 WK-PARAMETROS.
          05 WK-BB-NR-CT-CRT           PIC S9(17) USAGE COMP-3.
          05 WK-BB-NR-SEQL-TITD-PORT   PIC S9(09) USAGE COMP-3.
          05 WK-BB-CD-SUB-MDLD-CRT     PIC S9(04) USAGE COMP.
          05 WK-BB-IN-GR-158           PIC X(01) VALUE 'N'.
          05 WK-BB-TAB-ANUIDADE.
             07 WK-BB-CD-ANUD              PIC S9(4) USAGE COMP.
             07 WK-BB-IN-CBR-PRO-RATD      PIC X(1).
             07 WK-BB-IN-CBR-APVC-DEB      PIC X(1).
             07 WK-BB-DT-INC-VGC           PIC X(10).
             07 WK-BB-DT-FIM-VGC           PIC X(10).
             07 WK-BB-VL-PCL-TIT          PIC S9(9)V9(2) USAGE COMP-3.
             07 WK-BB-VL-PCL-ADC          PIC S9(9)V9(2) USAGE COMP-3.
             07 WK-BB-QT-PCL-TIT           PIC S9(4) USAGE COMP.
             07 WK-BB-QT-PCL-ADC           PIC S9(4) USAGE COMP.
             07 WK-BB-TX-ANUD              PIC X(70).
             07 WK-BB-CD-MDU-LGC           PIC S9(4) USAGE COMP.
             07 WK-BB-NR-PRIO-ANUD         PIC S9(4) USAGE COMP.
             07 WK-BB-QT-AA-VLD-ANUD-A     PIC S9(4) USAGE COMP.
             07 WK-BB-QT-AA-CARE-ANUD-A    PIC S9(4) USAGE COMP.
             07 WK-BB-CD-NVL-ACSS          PIC S9(4) USAGE COMP.
             07 WK-BB-IN-ISN-ANUD          PIC  X(1).
          05 WK-BB-QT-AA-VLD-ANUD      PIC S9(05) USAGE COMP-3.
          05 WK-BB-QT-AA-CARE-ANUD     PIC S9(05) USAGE COMP-3.
          05 WK-BB-CODIGO-OCI          PIC S9(05) USAGE COMP-3.

      *    COPYBOOK AREA TRANFERENCIA DADOS ENTRE PROGRAMAS     ***       VRS115
-INC  VIPK081W
      *                                                                   VRS115
      ******************************************************************  VRS115
      *                   Tabela de descontos                          *  VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       01 WS-TABELA-DESCONTO.
          05 TAB-DESCONTO              VALUE  ZEROS.
             10 TAB-DESCONTO
                OCCURS 12 TIMES
                INDEXED BY WIN-DESC.
                15 FAIXA-DESCONTO      PIC S9(009).
                15 VALOR-DESCONTO      PIC S9(009).
      *                                                                   VRS115
       01 WS-TABELA-GRMDLD.
          05 TAB-GRMDLD                VALUE  ZEROS.
             10 TAB-GRMDLD
                OCCURS 20 TIMES
                INDEXED BY WIN-GRMDLD.
                15 TAB-CD-MDLD-CRT         PIC S9(004).
      *                                                                   VRS115
       01 WS-TABELA-GRMDNAC.
          05 TAB-GRMDNAC               VALUE  ZEROS.
             10 TAB-GRMDNAC
                OCCURS 20 TIMES
                INDEXED BY WIN-GRMDNAC.
                15 TAB-CD-MDLD-NAC         PIC S9(004).

      *                                                                   VRS115
      ******************************************************************  VRS115
      *                   Queries-Termino-Variaveis.                   *  VRS115
      ******************************************************************  VRS115

       01  GDA-MENSAGEM-SQL01.
           03  FILLER                  PIC X(40)      VALUE
              'ERRO DE SQL - AVISE DESIS - COMANDO = '.
           03  GDA-CURSOR              PIC X(15).

       01  GDA-MENSAGEM-SQL02.
           03  FILLER                  PIC X(40)      VALUE
              '                            SQLCODE = '.
           03  GDA-CODESQL             PIC ZZ999-.

      *----------------------------------------------------------------*  VRS115
       01  INICIO-QUERIES              PIC X(005)     VALUE 'QUERY'.
      *----------------------------------------------------------------*  VRS115
       LOCAL-STORAGE                        SECTION.

           EXEC  SQL
                 INCLUDE  SQLCA
           END-EXEC.

           EXEC SQL
                DECLARE CONTAS CURSOR WITH HOLD FOR
                 SELECT A.CD_CLI
                      , A.NR_CT_CRT
                      , A.CD_MDLD_CRT
                      , A.NR_CT_CRT_ANT
                      , A.DT_ABTR_CT                                      VRS122
                      , B.CD_TITD_PORT
                      , B.NR_SEQL_TITD_PORT
                      , B.CD_TIP_CBR_ANUD
                      , B.IN_CBR_ANUD
                      , B.DT_PRX_ANIV_ANUD
                      , B.DT_PRMO_CBR_ANUD
                      , B.DT_INC_CBR_ANUD
                      , B.NR_PCL_PND_ANUD
                      , B.VL_PCL_ANUD
                      , B.QT_TTL_PCL_ANUD
                      , B.NR_ULT_PLST_EMBD
                      , B.CD_SUB_MDLD_CRT
                      , B.CD_ANUD                                         VRS128
                      , B.VL_ANUD_FATD                                    VRS128
                   FROM DB2VIP.CT_CRT   A
                      , DB2VIP.PORT_CRT B
                  WHERE A.NR_CT_CRT          = B.NR_CT_CRT
                    AND A.NR_CT_CRT         >= :AUX-NR-CT-CRT
                    AND A.DD_VNCT_CT         = :GDA-DIA-VENCIMENTO
                    AND A.IN_ANUD            = 0
                    AND A.CD_TIP_RST_CRT_CRD <> 133
                    AND B.CD_TIP_CBR_ANUD    IN (2, 3)
                    AND B.IN_CBR_ANUD        = 'S'
                  ORDER BY A.NR_CT_CRT,
                           B.NR_SEQL_TITD_PORT

           END-EXEC.

           EXEC SQL
                DECLARE GRMDLD CURSOR FOR
                 SELECT CD_MDLD_CRT_CRD
                   FROM DB2VIP.MDLD_GR
                  WHERE CD_GR_MDLD    =  53
           END-EXEC.

           EXEC SQL
                DECLARE GRMDNAC CURSOR FOR
                 SELECT CD_MDLD_CRT_CRD
                   FROM DB2VIP.MDLD_GR
                  WHERE CD_GR_MDLD    =  434
           END-EXEC.

           EXEC SQL
                DECLARE DESCONTO CURSOR FOR
                 SELECT DT_VGC_DSC_ANUD,
                        VL_LIM_INC,
                        PC_DSC,
                        VL_DSC
                   FROM DB2VIP.DSC_ANUD
                  WHERE DT_VGC_DSC_ANUD =
                       (SELECT MAX(DT_VGC_DSC_ANUD)
                          FROM DB2VIP.DSC_ANUD
                         WHERE CD_ANUD          =  :CONTAS-CD-MDLD-CRT
                           AND DT_VGC_DSC_ANUD  <= :GDA-DATA-ATUAL)
                    AND CD_ANUD         = :CONTAS-CD-MDLD-CRT
                   ORDER BY VL_LIM_INC
           END-EXEC.

           EXEC SQL
                DECLARE DSC-SUB   CURSOR FOR
                 SELECT DT_VGC_SUB_MDLD
                      , VL_LIM_SUB_MDLD
                      , PC_DSC_SUB_MDLD
                      , VL_DSC_SUB_MDLD
                   FROM DB2VIP.DSC_ANUD_SUB_MDLD
                  WHERE DT_VGC_SUB_MDLD =
                        (SELECT MAX(DT_VGC_SUB_MDLD)
                           FROM DB2VIP.DSC_ANUD_SUB_MDLD
                          WHERE CD_MDLD_CRT_CRD   = :GDA-CD-MDLD-CRT-CRD
                            AND CD_SUB_MDLD_CRT   = :GDA-CD-SUB-MDLD-CRT
                            AND DT_VGC_SUB_MDLD  <= :GDA-DATA-ATUAL)
                    AND CD_MDLD_CRT_CRD   = :GDA-CD-MDLD-CRT-CRD
                    AND CD_SUB_MDLD_CRT   = :GDA-CD-SUB-MDLD-CRT
                   ORDER BY VL_LIM_SUB_MDLD
           END-EXEC.

           EXEC SQL
                DECLARE PROMOCAO CURSOR WITH HOLD FOR
                 SELECT QT_AA_VLD_ANUD,
101219                  CD_ANUD                                           VRS115
                   FROM DB2VIP.ANUD_PORT
                  WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                    AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.

           EXEC SQL
                DECLARE CICLO CURSOR WITH HOLD FOR
                 SELECT DT_FATM_CT_CRT,
                        DT_PRVT_VNCT_FAT
                   FROM DB2VIP.CLDR_FATM
                  WHERE DT_FATM_CT_CRT = :GDA-DATA-FUTURA
                    AND CD_ORGZ_CT_CRT = 100
                  ORDER BY DT_PRVT_VNCT_FAT
           END-EXEC.

           EXEC SQL                                                       VRS121
                DECLARE GREXCO CURSOR FOR                                 VRS121
                 SELECT CD_MDLD_CRT_CRD                                   VRS121
                   FROM DB2VIP.MDLD_GR                                    VRS121
                  WHERE CD_GR_MDLD    = 1127                              VRS121
           END-EXEC.                                                      VRS121
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
       PROCEDURE DIVISION.
      *----------------------------------------------------------------*  VRS115

      *----------------------------------------------------------------*  VRS115
      *----------------------------------------------------------------*  VRS115
      *
           CALL  SBCPU     USING NOME-CPU.
      *
      *                                                                   VRS133
           IF  RETURN-CODE NOT EQUAL 0 OR GDA-MOCK = 1
             PERFORM 90090-00-MENSAGEM-ERRO-009
           END-IF.
      *                                                                   VRS133
           CALL SBVERSAO USING CTE-PROG CTE-VERS.

           MOVE 'INICIO PROCESS'       TO GDA-CURSOR.

           PERFORM 02000-00-BUSCA-DATA-PROC.
      *                                                                   VRS115
      * ---- > INICIO INCLUSAO DE PESQUISA GRUPO MDLD PARA PRIVATE        VRS115
      *                                                                   VRS115
           MOVE 'OPEN GRMDLD'           TO GDA-CURSOR.
           EXEC SQL
                OPEN GRMDLD
           END-EXEC.

           MOVE    ZEROS    TO   WIND-GRMDLD.
           PERFORM 19200-00-MONTA-TAB-GRMDLD
                   VARYING WIND-GRMDLD  FROM  1  BY  1
                   UNTIL   WIND-GRMDLD > 20.

           MOVE     ZEROS        TO  WIND-GRMDLD.
           MOVE 'CLOSE GRMDLD'   TO  GDA-CURSOR.
           EXEC SQL
                CLOSE GRMDLD
           END-EXEC.

           MOVE 'OPEN GRMDNAC'           TO GDA-CURSOR.
           EXEC SQL
                OPEN GRMDNAC
           END-EXEC.

           MOVE    ZEROS    TO   WIND-GRMDLD.
           PERFORM 19400-00-MONTA-TAB-GRMDNAC
                   VARYING WIND-GRMDLD  FROM  1  BY  1
                   UNTIL   WIND-GRMDLD > 20.

           MOVE     ZEROS        TO  WIND-GRMDLD.
           MOVE 'CLOSE GRMDNAC'  TO  GDA-CURSOR.
           EXEC SQL
                CLOSE GRMDNAC
           END-EXEC.

           PERFORM VARYING WIND FROM 1 BY 1 UNTIL WIND GREATER 100        VRS121
               MOVE ZEROS TO  TAB-CD-MDLD-EXCO(WIND)                      VRS121
           END-PERFORM                                                    VRS121
      *
           EXEC SQL                                                       VRS121
                OPEN GREXCO                                               VRS121
           END-EXEC.                                                      VRS121
      *
           PERFORM 31000-00-MONTA-TAB-EXCO                                VRS121
                   VARYING WIND  FROM  1  BY  1                           VRS121
                      UNTIL   FIM-EXCO.                                   VRS121
      *
           EXEC SQL                                                       VRS121
                CLOSE GREXCO                                              VRS121
           END-EXEC.                                                      VRS121
      *                                                                   VRS115
      * ---- > FINAL INCLUSAO DE PESQUISA GRUPO MDLD PARA PRIVATE         VRS115
      *                                                                   VRS115

           PERFORM 02500-00-OBTEM-DADOS-PROCESSO.
      ***                                                                 VRS115
      ***  Abre arquivo para conferencia do processamento                 VRS115
      ***                                                                 VRS115
           OPEN OUTPUT VIPFERRO
                       VIPFCANU
                       VIPF007S
                       VIPFSANU
                       VIPFANUD.
      ******************************************************************  VRS115
      *                                                                   VRS115
      ***  ----------------------------------------------------------     VRS115
      ***  Data do ultimo processamento completo do programa VIPP0007     VRS115
      ***  ----------------------------------------------------------     VRS115
           MOVE GDA-VIP-ANO            TO GDA-VIP-ANO-INV
           MOVE GDA-VIP-MES            TO GDA-VIP-MES-INV
           MOVE GDA-VIP-DIA            TO GDA-VIP-DIA-INV.

      ***  Data do processamento atual (gera 1 dia antes da fatura)       VRS115
      ***  --------------------------------------------------------       VRS115
           MOVE GDA-FUT-ANO            TO GDA-INV-ANO
           MOVE GDA-FUT-MES            TO GDA-INV-MES
           MOVE GDA-FUT-DIA            TO GDA-INV-DIA.
      *                                                                   VRS115
           IF  GDA-DATA-VIP-INV NOT LESS GDA-DATA-FUT-INVER
               MOVE 9000               TO RETURN-CODE
               DISPLAY '9000' CTE-PROG ' Rotina de calculo de anuidade '
               DISPLAY '9000' CTE-PROG ' ja foi processada para a data '
               DISPLAY '9000' CTE-PROG ' DT-VIP - ' GDA-DATA-VIP-INV
               DISPLAY '9000' CTE-PROG ' DT-FUT - ' GDA-DATA-FUT-INVER
               STOP RUN
           END-IF.
      *                                                                   VRS115
           MOVE ZEROS                  TO WCONTROL-CICLO.

           DISPLAY 'DATA DE HOJE              ' GDA-DATA-ATUAL.
           DISPLAY 'DATA PREVISTA PROX EXECUCAO     ' GDA-DATA-VIP7.
           DISPLAY 'DATA DO CICLO DAS FATURAS ' GDA-DATA-FUTURA.

           MOVE 'OPEN CICLO'           TO GDA-CURSOR.

           EXEC SQL
                OPEN CICLO
           END-EXEC.
      *                                                                   VRS115
           PERFORM 03000-00-VER-SE-TEM-CICLO
                   UNTIL GDA-CTRL EQUAL 1.

           MOVE 'CLOSE CICLO'          TO GDA-CURSOR.

           EXEC SQL
                CLOSE CICLO
           END-EXEC.

           IF GDA-CTRL EQUAL 1 AND
              WCONTROL-CICLO EQUAL ZEROS
              MOVE 0000                TO RETURN-CODE
              DISPLAY '0000' CTE-PROG ' NAO HA CICLO AGENDADO P/ HOJE'
              DISPLAY '0000' CTE-PROG ' ********* FIM NORMAL ********'
              STOP RUN
           END-IF.

           MOVE 'FAZ COMMIT'           TO GDA-CURSOR.

           EXEC SQL
                COMMIT
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

           MOVE 0                      TO RETURN-CODE.

           MOVE GDA-DATA-FUTURA        TO 207-VL-TIP-DT.
           MOVE 0                      TO CONTAS-NR-CT-CRT
                                          207-QT-DCML.

           PERFORM 14500-00-ATUALIZA-LIDER.
      *                                                                   VRS115
           PERFORM 30000-00-FINALIZA-REFNUMBER.
      *                                                                   VRS115
      ******************** Demanda 74729, Acao 29276 *******************  VRS115
      ***                                                                 VRS115
      ***  Fecha arquivos de conferencia                                  VRS115
      *                                                                   VRS115
           CLOSE VIPFERRO
                 VIPFCANU
                 VIPF007S
                 VIPFSANU
                 VIPFANUD.
      ******************************************************************  VRS115
           MOVE GDA-REG-DSC-ENCT                  TO MSK-REG-DSC-ENCT     VRS120
           DISPLAY '0000 *** Ciclos processados: ' WCONTROL-CICLO.
           DISPLAY '0000 *** Reg. Gravados no movimento: ' WGRAVADOS.
           DISPLAY '0000 *** VIPF007 GRAVADOS: ' CNT-REG-VIPF007.
           DISPLAY '0000 *** VIPANUD GRAVADOS: ' GDA-REG-GRAV-ANUD.
           DISPLAY '0000 *** Descontos Concedidos: ' MSK-REG-DSC-ENCT.    VRS120
           DISPLAY '0000 *** Port com INV min: ' CNT-PORT-INV-ATDG
           DISPLAY '0000 *** Port sem INV min: ' CNT-PORT-INV-N-ATDG
           DISPLAY '0000 *** Descontos Concedidos: ' CNT-PORT-INV-N-ATDG
           DISPLAY '0000 ' CTE-PROG 'Fim Normal ***'.

           STOP RUN.

      *----------------------------------------------------------------*  VRS115
       02000-00-BUSCA-DATA-PROC        SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'BUSCA DATA-PROC'      TO GDA-CURSOR.

      *     MOVE 'VIPP0007'             TO WS-ABEND-PROG-ID.              VRS115

           IF NOME-CPU  EQUAL 'HOMA' OR 'HOMB'                            VRS133
             MOVE 'DTFUTHM '           TO 207-NM-PRM
           ELSE
             MOVE 'DTFUT   '           TO 207-NM-PRM
           END-IF

           MOVE 'VIP'                  TO 207-CD-SIST


           EXEC  SQL
                 SELECT VL_TIP_DT
                   INTO :207-VL-TIP-DT:INULL-VL-TIP-DT
                   FROM DB2VIP.LIDER
                  WHERE CD_SIST = :207-CD-SIST
                    AND NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90040-00-MENSAGEM-ERRO-004
           END-IF.

           MOVE 207-VL-TIP-DT          TO GDA-DATA-FUTURA.

      *-----------------------------------------------------------------  VRS115
      * ALTERACAO POR POSSIVEL EXECUCAO APOS A EXECUCAO DA PVIPD080,      VRS115
      * SE A PVIPD080 DO DIA JA ESTIVER RODADO, A DATA-ATUAL SERA DE D+1  VRS115
      *-----------------------------------------------------------------  VRS115
      *    MOVE 'VIP'                  TO 207-CD-SIST.                    VRS115
      *    MOVE 'DTATU   '             TO 207-NM-PRM.                     VRS115
      *-----------------------------------------------------------------  VRS115
           MOVE 'CPP'                  TO 207-CD-SIST.
           MOVE 'DTFUTCPP'             TO 207-NM-PRM.
      *-----------------------------------------------------------------  VRS115

           EXEC  SQL
                 SELECT VL_TIP_DT
                   INTO :207-VL-TIP-DT:INULL-VL-TIP-DT
                   FROM DB2VIP.LIDER
                  WHERE CD_SIST = :207-CD-SIST
                    AND NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90040-00-MENSAGEM-ERRO-004
           END-IF.

           MOVE 207-VL-TIP-DT          TO GDA-DATA-ATUAL.

      *    Busca sequencial para REFERENCE NUMBER....                     VRS115
      *                                                                   VRS115
           MOVE 'ANU'                  TO 207-CD-SIST.
           MOVE 'REFNUMAN'             TO 207-NM-PRM.

           EXEC  SQL
                 SELECT VL_TIP_NR
                   INTO :207-VL-TIP-NR
                   FROM DB2VIP.LIDER
                  WHERE CD_SIST = :207-CD-SIST
                    AND NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90050-00-MENSAGEM-ERRO-005
           END-IF.

           MOVE 207-VL-TIP-NR          TO GDA-SEQL-REFNUM.
      *
           MOVE 'VIP'                  TO 207-CD-SIST.                    VRS122
           MOVE 'DTABTDAA'             TO 207-NM-PRM.                     VRS122
      *
           EXEC  SQL                                                      VRS122
                 SELECT  VL_TIP_DT                                        VRS122
                   INTO :207-VL-TIP-DT:INULL-VL-TIP-DT                    VRS122
                   FROM DB2VIP.LIDER                                      VRS122
                  WHERE CD_SIST = :207-CD-SIST                            VRS122
                    AND NM_PRM  = :207-NM-PRM                             VRS122
           END-EXEC.                                                      VRS122
      *
           IF SQLCODE NOT EQUAL ZEROS                                     VRS122
              PERFORM 90040-00-MENSAGEM-ERRO-004                          VRS122
           END-IF.                                                        VRS122
      *
           MOVE 207-VL-TIP-DT(1:2) TO GDA-DTABTDAA-INV(7:2)               VRS122
           MOVE 207-VL-TIP-DT(4:2) TO GDA-DTABTDAA-INV(5:2)               VRS122
           MOVE 207-VL-TIP-DT(7:4) TO GDA-DTABTDAA-INV(1:4).              VRS122
       02000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       02500-00-OBTEM-DADOS-PROCESSO   SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'DADOS PROCESSO'       TO GDA-CURSOR.
           MOVE 'VIP'                  TO 207-CD-SIST.
           MOVE 'VIPP0007'             TO 207-NM-PRM.

           EXEC  SQL
                 SELECT VL_TIP_DT
                      , VL_TIP_NR
                      , QT_DCML
                   INTO :207-VL-TIP-DT:INULL-VL-TIP-DT
                      , :207-VL-TIP-NR
                      , :207-QT-DCML:INULL-QT-DCML
                   FROM DB2VIP.LIDER
                  WHERE CD_SIST = :207-CD-SIST
                    AND NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90040-00-MENSAGEM-ERRO-004
           END-IF.

           IF INULL-QT-DCML  LESS  ZEROS
              MOVE ZEROS               TO 207-QT-DCML
           END-IF.

           MOVE 207-VL-TIP-DT          TO GDA-DATA-VIP7.
           MOVE 207-VL-TIP-NR          TO WPONTO-RESTART
                                          AUX-NR-CT-CRT.

       02500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       03000-00-VER-SE-TEM-CICLO       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'VERIFICA CICLO'       TO GDA-CURSOR.

           EXEC SQL
                FETCH CICLO
                 INTO :GDA-DATA-EFETIVA:INULL-DT-EFT
                    , :GDA-DTA-VENC
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE NOT EQUAL +100
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              ELSE
                 MOVE 1                TO GDA-CTRL
                 MOVE 9                TO 207-QT-DCML
              END-IF
           END-IF.

           IF 207-QT-DCML NOT EQUAL 9
              ADD 1                    TO GDA-CTRL-CICLO
           END-IF.

           IF  207-QT-DCML NOT GREATER GDA-CTRL-CICLO

           IF  207-QT-DCML NOT EQUAL GDA-CTRL-CICLO
               MOVE ZEROS              TO WPONTO-RESTART
           END-IF
      * >>> asteriscar
           IF  INULL-DT-EFT   LESS  ZEROS AND
               WCONTROL-CICLO EQUAL ZEROS
               MOVE 9000               TO RETURN-CODE
               DISPLAY '9000' CTE-PROG ' Nao foi executado o programa'
               DISPLAY '9000' CTE-PROG '  VIPP0234 Procedure PVIPD261'
               STOP RUN
           ELSE
               IF INULL-DT-EFT   LESS    ZEROS AND
                  WCONTROL-CICLO GREATER ZEROS
                  MOVE 9000            TO RETURN-CODE
               DISPLAY '9000' CTE-PROG ' Problema na execucao do Prog.'
               DISPLAY '9000' CTE-PROG ' VIPP0234 Procedure  PVIPD261 '
                  STOP RUN
               END-IF
           END-IF
      * asteriscar <<<
      ***  Monta dia de vencimento (Obtido no cursor CICLO da tabela      VRS115
      ***  CLDR_FATM) para utilizacao no cursor CONTAS.                   VRS115
      ***  ----------------------------------------------------------     VRS115
           MOVE GDA-VEN-DIA            TO GDA-DIA-VENCIMENTO
           ADD 1                       TO WCONTROL-CICLO


      ***  Efetua os calculos de Anuidade para os portadores com          VRS115
      ***  vencimento neste dia.                                          VRS115
      ***  ----------------------------------------------------------     VRS115
      ***                                                                 VRS115
      ******************** Demanda 74729, Acao 29276 *******************  VRS115
      ***                                                                 VRS115
      ***  Abre arquivo com as contas cartao cadastradas no vision        VRS115
      ***                                                                 VRS115
           OPEN INPUT  VIPF904E
      *                                                                   VRS115
           MOVE 0  TO  FIM-VIPF904
                       PRIMEIRA-VEZ
      *                                                                   VRS115
      ***                                                                 VRS115
      ***  Ler header do arquivo VIPF904 e descarta os registros          VRS115
      ***  com conta cartao zerada - registros irregulares                VRS115
      *                                                                   VRS115
           MOVE ZEROS TO 904-NR-CT-CRT
                         FIM-VIPF904

           PERFORM 250000-00-LER-ARQ-VIPF904E
              UNTIL (904-NR-CT-CRT NOT EQUAL ZEROS
                 AND 904-COD-BLOQ      EQUAL SPACES)
                 OR FIM-VIPF904    = 1

           IF FIM-VIPF904    = 1
              DISPLAY '######## Demanda 74729, Acao 29276 #####'
              DISPLAY 'Arquivo VIPF904E estah com todos os seus regis'
                      'tros com conta cartao zerada'
              DISPLAY '########################################'
           ELSE
              MOVE 904-NR-CT-CRT TO WS-NR-CT-CRT
              DISPLAY '######## Demanda 74729, Acao 29276 #####'
              DISPLAY 'Primeira conta do arquivo VIPF904E ---> '
                      WS-NR-CT-CRT
              DISPLAY '########################################'
           END-IF
      *                                                                   VRS115
           PERFORM 03500-00-ROTINA-CALCULO
      ***                                                                 VRS115
      ******************** Demanda 74729, Acao 29276 *******************  VRS115
      ***                                                                 VRS115
      ***  Fecha arquivo com as contas cartao cadastradas no vision       VRS115
      ***                                                                 VRS115
           CLOSE VIPF904E

           END-IF.

       03000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       03500-00-ROTINA-CALCULO         SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'ROTINA CALCULO'       TO GDA-CURSOR.

           PERFORM 04000-00-MONTA-DATA-FINAL.

           MOVE SPACES                 TO WCONTROL-LEITURA.
           MOVE ZEROS                  TO CONTAS-NR-CT-CRT.

           MOVE 'OPEN CONTAS'          TO GDA-CURSOR.
           EXEC SQL
                OPEN CONTAS
           END-EXEC.

           PERFORM 05000-00-TESTA-REGISTROS
                   UNTIL WCONTROL-LEITURA EQUAL '*'.

           MOVE 'CLOSE CONTAS'         TO GDA-CURSOR.

           EXEC SQL
                CLOSE CONTAS
           END-EXEC.

       03500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       04000-00-MONTA-DATA-FINAL       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'MONTA DATA-FIM'       TO GDA-CURSOR.

           MOVE GDA-ATU-MES            TO IND-EH-MES
                                          GDA-AMD-MES.
           MOVE GDA-ATU-ANO            TO GDA-AMD-ANO.

           IF EH-MES-31
              MOVE 31                  TO GDA-AMD-DIA
           END-IF.

           IF EH-MES-30
              MOVE 30                  TO GDA-AMD-DIA
           END-IF.

           IF GDA-AMD-MES EQUAL 2
              DIVIDE GDA-AMD-ANO       BY 4 GIVING DIVI
                                       REMAINDER RESTO
              IF RESTO = 0
                 MOVE 29               TO GDA-AMD-DIA
              ELSE
                 MOVE 28               TO GDA-AMD-DIA
              END-IF
           END-IF.

       04000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       05000-00-TESTA-REGISTROS        SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'TESTA REGISTRO'       TO GDA-CURSOR.

           PERFORM 06000-00-LER-CONTAS
                   UNTIL CONTAS-NR-CT-CRT GREATER WPONTO-RESTART.
      *                                                                   VRS115
           IF WCONTROL-LEITURA NOT EQUAL '*'
      ***                                                                 VRS115
      ******************** Demanda 74729, Acao 29276 *******************  VRS115
      ***                                                                 VRS115
      *                                                                   VRS115
      *------Verifica no arquivo VIPF904E - copia resumida do AMBS -      VRS115
      *------se as contas cartoes passiveis de cobranca de anuidade       VRS115
      *------jah efetivaram alguma compra no cartao funcao credito.       VRS115
      *------Caso jah tenham efetivado alguma compra, poderah cobrar      VRS115
      *------anuidade, caso contrario nao.                                VRS115
      *                                                                   VRS115
             MOVE CONTAS-NR-CT-CRT-ANT TO GDA-NR-CT-CRT-ANT

             MOVE CONTAS-DT-ABTR-CT(1:2) TO GDA-DT-ABTR-CT-INV(7:2)       VRS122
             MOVE CONTAS-DT-ABTR-CT(4:2) TO GDA-DT-ABTR-CT-INV(5:2)       VRS122
             MOVE CONTAS-DT-ABTR-CT(7:4) TO GDA-DT-ABTR-CT-INV(1:4)       VRS122

             PERFORM 250000-00-LER-ARQ-VIPF904E
               UNTIL (904-NR-CT-CRT >= CONTAS-NR-CT-CRT
                  AND 904-COD-BLOQ  = SPACES)
                  OR FIM-VIPF904    = 1
      *
             IF FIM-VIPF904   = 1
             OR 904-NR-CT-CRT > CONTAS-NR-CT-CRT
      *                                                                   VRS115
      *------Demanda 74729, Acao 29276 - Conta cartao do VIP nao          VRS115
      *------encontrada no arquivo AMBS                                   VRS115
      *                                                                   VRS115
             IF  FIM-VIPF904   = 1
             AND PRIMEIRA-VEZ  = 0
                MOVE CONTAS-NR-CT-CRT    TO WS-NR-CT-CRT
                MOVE 1                   TO PRIMEIRA-VEZ
                DISPLAY '######## Demanda 74729, Acao 29276 #####'
                DISPLAY 'Arquivo VIPF904E finalizou pesquisando a conta'
                        ' ---> '  WS-NR-CT-CRT
                DISPLAY '########################################'
             END-IF
      *      PERFORM 90050-00-MENSAGEM-ERRO-005                           VRS115
      *                                                                   VRS115
      *------Demanda 74729, Acao 29276 - Grava um arquivo sequencial      VRS115
      *------com todas as contas existentes no DB2 do VIP e nao           VRS115
      *------encontrada no arquivo AMBS do VISION para analise futura     VRS115
      *------do analista responsavel                                      VRS115
      *                                                                   VRS115
               PERFORM 260000-00-GRAVA-VIPFERRO
      *                                                                   VRS115
             END-IF
      *                                                                   VRS115
      *------Demanda 74729, Acao 29276 - Soh cobrar anuidade do cliente   VRS115
      *------caso ele jah tenha efetuado alguma compra no cartao          VRS115
      *                                                                   VRS115
             IF  ( 904-NR-CT-CRT         = CONTAS-NR-CT-CRT  AND
                   904-DT-PRI-COMPRA NOT = 01010001          AND
                   FIM-VIPF904           = 0 )
                 OR
                 ( 904-NR-CT-CRT         = CONTAS-NR-CT-CRT  AND
                   FIM-VIPF904           = 0                 AND
                   GDA-IND-BNC           = 1 )

      *--------Para clientes migrados do BNC em 13/07/2010 não será       VRS115
      *--------considerada a data da primeira compra ou saque.            VRS115
      *                                                                   VRS115
      *--------Cliente jah fez compras no cartao, logo estah apto a       VRS115
      *--------cobranca de anuidade                                       VRS115
      *                                                                   VRS115
      *                                                                   VRS115
      *--------Grava arquivo com todas as contas que jah efetivaram       VRS115
      *--------compras e que estao aptas a cobrar anuidade                VRS115
      *                                                                   VRS115
               PERFORM 270000-00-GRAVA-VIPFCANU
      *                                                                   VRS115
               PERFORM 07000-00-MODULO-SELECAO
             END-IF
      *                                                                   VRS115
             IF  904-NR-CT-CRT         = CONTAS-NR-CT-CRT
             AND 904-DT-PRI-COMPRA     = 01010001
             AND FIM-VIPF904           = 0
      *                                                                   VRS115
      *--------Grava arquivo com todas as contas que jah ainda            VRS115
      *--------nao efetivaram compras e que estao aptas a cobrar          VRS115
      *--------anuidade                                                   VRS115
      *                                                                   VRS115
               PERFORM 280000-00-GRAVA-VIPFSANU
      *                                                                   VRS115
             END-IF
      *                                                                   VRS115
      *------Ler proxima conta cartao para provavel cobranca de anuidade  VRS115
      *                                                                   VRS115
             PERFORM 06000-00-LER-CONTAS
           END-IF.
      ***                                                                 VRS115
      ******************** Demanda 74729, Acao 29276 *******************  VRS115
      ***                                                                 VRS115
      *                                                                   VRS115
      *----Codigo fonte antigo virou comentario - HISTORICO               VRS115
      *                                                                   VRS115
      *    IF WCONTROL-LEITURA NOT EQUAL '*'                              VRS115
      *       PERFORM 07000-00-MODULO-SELECAO                             VRS115
      *       PERFORM 06000-00-LER-CONTAS                                 VRS115
      *    END-IF.                                                        VRS115
      ******************************************************************  VRS115
      *                                                                   VRS115
       05000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       06000-00-LER-CONTAS             SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'FETCH CONTAS'         TO GDA-CURSOR.

           EXEC SQL
                FETCH CONTAS
                 INTO :CONTAS-CD-CLI
                    , :CONTAS-NR-CT-CRT
                    , :CONTAS-CD-MDLD-CRT
                    , :CONTAS-NR-CT-CRT-ANT
                    , :CONTAS-DT-ABTR-CT                                  VRS122
                    , :CONTAS-CD-TITD-PORT
                    , :CONTAS-NR-SEQL-TITD-PORT
                    , :CONTAS-CD-TIP-CBR-ANUD
                    , :CONTAS-IN-CBR-ANUD
                    , :CONTAS-DT-PRX-ANIV-ANUD
                    , :CONTAS-DT-PRMO-CBR-ANUD
                    , :CONTAS-DT-INC-CBR-ANUD
                    , :CONTAS-NR-PCL-PND-ANUD
                    , :CONTAS-VL-PCL-ANUD
                    , :CONTAS-QT-TTL-PCL-ANUD
                    , :CONTAS-NR-PLST
                    , :CONTAS-CD-SUB-MDLD-CRT
                    , :CONTAS-CD-ANUD-LIDO                                VRS128
                    , :CONTAS-VL-ANUD-FATD                                VRS128
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE NOT EQUAL +100
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              ELSE
                 MOVE '*'              TO WCONTROL-LEITURA
                 MOVE 999999999        TO CONTAS-NR-CT-CRT
              END-IF
           END-IF.

           MOVE CONTAS-CD-MDLD-CRT     TO GDA-CD-MDLD-CRT-CRD.
           MOVE CONTAS-CD-SUB-MDLD-CRT TO GDA-CD-SUB-MDLD-CRT
                                          GDA-SUB-MDLD.
       06000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       07000-00-MODULO-SELECAO         SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'MOD. SELECAO'          TO GDA-CURSOR.
      *
           IF 904-PC-DSC-ANUD-CTRA NOT = 0 OR
              904-PC-DSC-ANUD-INV NOT = 0
              PERFORM VARYING WIND FROM 1 BY 1 UNTIL WIND GREATER 100     VRS121
                 IF TAB-CD-MDLD-EXCO(WIND) = 0                            VRS121
                    MOVE 9999 TO WIND                                     VRS121
                 ELSE                                                     VRS121
                    IF TAB-CD-MDLD-EXCO(WIND) = CONTAS-CD-MDLD-CRT        VRS121
                       MOVE ZEROS TO  904-PC-DSC-ANUD-CTRA
                                      904-PC-DSC-ANUD-INV
                       MOVE 9999 TO WIND                                  VRS121
                    END-IF                                                VRS121
                 END-IF                                                   VRS121
              END-PERFORM                                                 VRS121
           END-IF                                                         VRS121
      *
           PERFORM 08000-00-OBTEM-DADOS-ANUIDADE.
      *
           MOVE CONTAS-CD-TIP-CBR-ANUD  TO GDA-CD-TIP-CBR-ANUD.
           MOVE CONTAS-IN-CBR-ANUD      TO GDA-IN-CBR-ANUD.
           MOVE CONTAS-DT-PRX-ANIV-ANUD TO GDA-DATA-DB2.
           MOVE GDA-DB2-DIA             TO GDA-AMD-DIA-T.
           MOVE GDA-DB2-MES             TO GDA-AMD-MES-T.
           MOVE GDA-DB2-ANO             TO GDA-AMD-ANO-T.
      *
           IF IND-ERRO NOT EQUAL ZEROS
              GO TO 07000-99-EXIT
           END-IF.
           MOVE 'MOD. CALCULO'          TO GDA-CURSOR.

           MOVE SPACE                   TO F007-TIP-REG.
           MOVE SPACES                  TO F007-DT-MVT-ANUD.

           MOVE 0                       TO F007-NR-CT-CRT.
           MOVE 0                       TO F007-NR-SEQL-TITD-PORT.
           MOVE 0                       TO F007-VL-ANUD-CBR.
           MOVE 0                       TO F007-VL-DSC-ANUD.
      **                                                                  VRS115
      ****************************************************************    VRS115
      **  Verifica:                                                       VRS115
      **  .se data proximo aniversario eh menor ou igual ao               VRS115
      **   ultimo dia do mes (c-12);                                      VRS115
      **  .se a conta esta em processo normal de cobranca (c-15);         VRS115
      **  .se eh a primeira cobranca da existencia da conta (c-18);       VRS115
      **  .se conta eh Ratificacao de Debito (c-21);                      VRS115
      **  .se na primeira cobranca a conta tem direito a                  VRS115
      **   carencia (c-27);                                               VRS115
      **                                                                  VRS115
      *****************************************************************   VRS115
      **                                                             **   VRS115
      **   P A R T E   I    -    TRATA INICIO DE UM NOVO PERIODO DE  **   VRS115
      **                         COBRANCA DE ANUIDADE PARA CONTA.    **   VRS115
      **                                                             **   VRS115
      *****************************************************************   VRS115
      *
      * MOCK-POINT FORCA-ERRO-004
      *
           IF GDA-AMD-TEMP NOT GREATER GDA-AMD-FINAL
              AND CONTAS-NR-PCL-PND-ANUD = 0
              IF CONTAS-CD-TIP-CBR-ANUD EQUAL 2
                 IF GDA-AMD-TEMP EQUAL 00010101 AND
                    CONTAS-DT-INC-CBR-ANUD EQUAL '01.01.0001'
                    IF 140-IN-CBR-APVC-DEB EQUAL 'S'
      **  Inibicao de procedimento referente a Ratificacao de Debito. **  VRS115
      **      Controle serah realizado pelo indicador IN_ANUD.        **  VRS115
      **                   20.Julho.2001                              **  VRS115
      ***              PERFORM 09000-00-TRATA-MOVIMENTO                   VRS115
      ***              IF GDA-SDO-CONTA GREATER ZEROS                     VRS115
                          IF 140-QT-AA-CARE-ANUD GREATER ZEROS
                             PERFORM 10000-00-ATUALIZA-CARENCIA
                             GO TO 07000-99-EXIT
                          END-IF
      ***              ELSE                                               VRS115
      ***                 GO TO 07000-99-EXIT                             VRS115
      ***              END-IF                                             VRS115
                    ELSE
      * >>> asteriscar
      ****************************************************************    VRS115
      **  Caso nao seja ratificacao de debito verifica se conta tem       VRS115
      **  direito a carencia na primeira cobranca da existencia.          VRS115
      ****************************************************************    VRS115
                       IF 140-QT-AA-CARE-ANUD GREATER ZEROS
                          PERFORM 10000-00-ATUALIZA-CARENCIA
                          GO TO 07000-99-EXIT
                       END-IF
      * asteriscar <<<
                    END-IF
                 END-IF
              END-IF

      ****************************************************************    VRS115
      **  Tratamento especial para conta com cobranca suspensa.           VRS115
      **  A suspensao sera alterada caso se verifique exitencia de        VRS115
      **  utilizacao do cartao para algum saque ou compra.                VRS115
      ****************************************************************    VRS115
      ***     IF CONTAS-CD-TIP-CBR-ANUD EQUAL 3                           VRS115
      ***        PERFORM 09000-00-TRATA-MOVIMENTO                         VRS115
      ***        IF GDA-SDO-CONTA = 0                                     VRS115
      ***           GO TO 07000-99-EXIT                                   VRS115
      ***        END-IF                                                   VRS115
      ***        MOVE 2                TO GDA-CD-TIP-CBR-ANUD             VRS115
      ***     END-IF                                                      VRS115

      ****************************************************************    VRS115
      * Tratamento diferenciado para contas de cartoes Empresariais  *    VRS115
      * Deve ser alterado sempre que for criada modalidade com esta  *    VRS115
      * caracteristica, ou seja, sem titularidade igual a 1.         *    VRS115
      * Teste efetuado quando inicio de cobranca de um novo periodo. *    VRS115
      ****************************************************************    VRS115
      *                                                                   VRS115
              IF NOT (CONTAS-CD-MDLD-CRT EQUAL 03 OR 07 OR 31 OR 32
                    OR 33 OR 34 OR 41 OR 42 OR 43 OR 56 OR 57 OR 58
                    OR 71 OR 82 OR 95 OR 96 OR 114 OR 185 OR 186
                    OR 97 OR 191 OR 197)

                 IF CONTAS-CD-TITD-PORT NOT EQUAL 1
                    PERFORM 11000-00-OBTEM-TITULAR
                    IF SQLCODE EQUAL +100
                       GO TO 07000-99-EXIT
                    END-IF
                 END-IF
                 PERFORM 12000-00-CALCULA-ANUIDADE
              ELSE
                 PERFORM 15100-01-VERIFICA-DSC-SUB
                 IF IND-DSC-SUB = 'N'
                    PERFORM 15000-00-CALCULA-PRIMEIRA
                 ELSE
                    PERFORM 15000-00-CALC-PRIM-SUB
                 END-IF
              END-IF
      ******************************************************************
      * Parcela de anuidade maior que zero
      * titular com 100% de desconto na primeira parcela
      * não inicia novo ciclo de cobrança de anuidade
      ******************************************************************
              IF GDA-VL-ANUD EQUAL ZEROS        AND
                 140-VL-PCL-TIT GREATER ZEROS   AND
                 CONTAS-CD-TITD-PORT EQUAL 1
                 GO TO 07000-99-EXIT
              END-IF

      ******************************************************************
      * Parcela de anuidade maior que zero
      * portador com 100% de desconto na primeira parcela
      * não inicia novo ciclo de cobrança de anuidade
      ******************************************************************
              IF GDA-VL-ANUD EQUAL ZEROS        AND
                 140-VL-PCL-ADC GREATER ZEROS   AND
                 CONTAS-CD-TITD-PORT GREATER 1
                 GO TO 07000-99-EXIT
              END-IF
      * >>> asteriscar
      ******************************************************************
      * a tabela de anuidades diferenciadas - promocao (anud_port)
      * deve ser atualizada no inicio de cada ciclo, uma vez que nao
      * se pode assegurar que um portador chegará ao final de um
      * determinado ciclo, pois em caso de interrupcao de ciclo de
      * anuidade, um novo ciclo se inicia posteriormente, sem que o
      * ciclo que foi interrompido seja finalizado.
      ******************************************************************  VRS115
      * Isencao de cobranca de anuidade para o titular em decorrencia     VRS115
      *                  de promocao. Condicao Normal.                    VRS115
      ******************************************************************  VRS115
      *        IF GDA-VL-ANUD EQUAL ZEROS        AND
      *           140-VL-PCL-TIT EQUAL ZEROS     AND
      *           CONTAS-CD-TITD-PORT EQUAL 1
      *           MOVE 'A' TO F007-TIP-REG
      *           PERFORM 13000-00-ATUALIZA-TABS
      *           PERFORM 21000-00-ATUALIZA-PROMOCAO
      *           GO TO 07000-99-EXIT
      *        END-IF
      ******************************************************************  VRS115
      * Isencao de cobranca de anuidade para o adicional em decorrencia   VRS115
      *                  de promocao. Condicao Normal.                    VRS115
      ******************************************************************  VRS115
      *        IF GDA-VL-ANUD EQUAL ZEROS        AND
      *           140-VL-PCL-ADC EQUAL ZEROS     AND
      *           CONTAS-CD-TITD-PORT GREATER 1
      *           MOVE 'A' TO F007-TIP-REG
      *           PERFORM 13000-00-ATUALIZA-TABS
      *           IF WPRORAT-DIF-DATAS NOT LESS 12
      *              PERFORM 21000-00-ATUALIZA-PROMOCAO
      *           END-IF
      *           GO TO 07000-99-EXIT
      *        END-IF
      * asteriscar <<<
      ******************************************************************  VRS115
      * Calculo de parcela negativo para titular ou adicional             VRS115
      * condicao de ERRO. Avaliar display.                                VRS115
      ******************************************************************  VRS115
              IF GDA-VL-ANUD LESS ZEROS
                 DISPLAY 'Valor Negativo - ' CONTAS-NR-CT-CRT ' / '
                                             CONTAS-CD-TITD-PORT
                 GO TO 07000-99-EXIT
              END-IF

              MOVE 'A' TO F007-TIP-REG
              PERFORM 13000-00-ATUALIZA-TABS
      ***  **************************************************  ***        VRS115
      ***  Atualiza tabela de promocoes  (ANUD_PORT)  somente  ***        VRS115
      ***  na cobranca  da  ultima parcela  de  anuidade para  ***        VRS115
      ***  permitir eventuais acertos de cobranca na situacao  ***        VRS115
      ***  em que foi iniciado o processo.                     ***        VRS115
      ***  **************************************************  ***        VRS115
              IF  WK-BB-CODIGO-OCI EQUAL ZEROS
                  PERFORM 21000-00-ATUALIZA-PROMOCAO
              END-IF
      *
      ****************************************************************    VRS115
      **  Nao eh inicio de um novo periodo de cobranca, ou seja,          VRS115
      **  eh a continuidade de um parcelamento da anuidade.               VRS115
      ****************************************************************    VRS115
           ELSE
      *****************************************************************   VRS115
      **                                                             **   VRS115
      **   P A R T E   II   -    TRATA CONTINUIDADE DE UM PROCESSO   **   VRS115
      **                         DE COBRANCA INICIADO.               **   VRS115
      **                                                             **   VRS115
      *****************************************************************   VRS115
              IF CONTAS-NR-PCL-PND-ANUD GREATER ZEROS
                 IF NOT (CONTAS-CD-MDLD-CRT EQUAL 03 OR 07 OR 31 OR 32
                       OR 33 OR 34 OR 41 OR 42 OR 43 OR 56 OR 57 OR 58
                       OR 71 OR 82 OR 95 OR 96 OR 114 OR 185 OR 186
                       OR 97 OR 191 OR 197)
                    PERFORM 12000-00-CALCULA-ANUIDADE
                 ELSE
                    PERFORM 15100-01-VERIFICA-DSC-SUB
                    IF IND-DSC-SUB = 'N'
                       PERFORM 15000-00-CALCULA-PRIMEIRA
                    ELSE
                       PERFORM 15000-00-CALC-PRIM-SUB
                    END-IF
                 END-IF

                 MOVE 'B' TO F007-TIP-REG
                 PERFORM 13000-00-ATUALIZA-TABS

      ***  **************************************************  ***        VRS115
      ***  Atualiza tabela  de  promocoes (ANUD_PORT) somente  ***        VRS115
      ***  na cobranca da ultima  parcela  de  anuidade  para  ***        VRS115
      ***  permitir eventuais acertos de cobranca na situacao  ***        VRS115
      ***  em que foi iniciado o processo.                     ***        VRS115
      ***  **************************************************  ***        VRS115
      *
                 IF WPARC-PEND EQUAL WPARC-TOTAL
                    AND WK-BB-CODIGO-OCI NOT EQUAL ZEROS
                    PERFORM 21000-00-ATUALIZA-PROMOCAO
                 END-IF
      *
              ELSE
      ** Verifica se portador isento esta EM periodo de cobranca          VRS115
      ** INICIO : Data de inclusao de cobranca                            VRS115
      ** FIM    : Data de inclusao de cobranca + (quantidade de parcelas  VRS115
      ** @@       da anuidade padrao - 1)meses                            VRS115
      ** -------------------------------------------------------          VRS115
                 PERFORM 07100-00-CALC-PERIODO-CBR

                 IF CONTAS-VL-PCL-ANUD EQUAL   ZEROS             AND
                    GDA-DT-ATU-N08 NOT LESS    GDA-DT-INI-CBR    AND
                    GDA-DT-ATU-N08 NOT GREATER GDA-DT-FIM-CBR
                    MOVE 'C'                  TO F007-TIP-REG
                    MOVE CONTAS-NR-CT-CRT     TO F007-NR-CT-CRT
                    MOVE CONTAS-NR-SEQL-TITD-PORT
                                              TO F007-NR-SEQL-TITD-PORT
                    MOVE ZEROS                TO F007-VL-ANUD-CBR
                                                 F007-VL-DSC-ANUD
                    MOVE GDA-DATA-ATUAL       TO F007-DT-MVT-ANUD
                    WRITE FD-REG-VIPF007
                    ADD 1 TO CNT-REG-VIPF007
                 END-IF
              END-IF
           END-IF.

       07000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       07100-00-CALC-PERIODO-CBR       SECTION.
      *----------------------------------------------------------------*  VRS115
      ** Se quantidade de parcelas do portador > 1 considera como period  VRS115
      **   de cobranca as parcelas do portador.                           VRS115
      ** Senao                                                            VRS115
      **   Busca quantidade de parcelas da anuidade padrao da modalidade  VRS115
      ** --------------------------------------------------------------   VRS115

           IF CONTAS-VL-PCL-ANUD     > 0 AND
              CONTAS-QT-TTL-PCL-ANUD > 1
              MOVE CONTAS-QT-TTL-PCL-ANUD     TO GDA-QT-PCL-PDAO
           ELSE

              PERFORM 15102-01-VIPST752-GR107

              IF IND-DSC-SUB EQUAL 'S'
                 MOVE  GDA-CD-MDLD-CRT-CRD   TO  748-CD-MDLD-CRT-CRD
                 MOVE  GDA-CD-SUB-MDLD-CRT   TO  748-CD-SUB-MDLD-CRT
                 MOVE  'ANUIDADE'            TO  748-CD-PRM

                 EXEC  SQL
                       SELECT  NR_CTU_PRM
                         INTO  :GDA-CD-ANUD-PDAO
                         FROM  DB2VIP.PRM_SUB_MDLD
                        WHERE  CD_MDLD_CRT_CRD = :748-CD-MDLD-CRT-CRD
                          AND  CD_SUB_MDLD_CRT = :748-CD-SUB-MDLD-CRT
                          AND  CD_PRM          = :748-CD-PRM
                 END-EXEC

                 IF SQLCODE NOT EQUAL ZEROS
                    PERFORM 90070-00-MENSAGEM-ERRO-021
                 END-IF

              ELSE
                 EXEC  SQL
                   SELECT A.VL_TIP_NUM
                   INTO   :GDA-CD-ANUD-PDAO
                   FROM   DB2VIP.PRM_MDLD_CRT_CRD A
                   WHERE  A.NM_PRM      = 'ANUIDADE'
                     AND  A.CD_MDLD_CRT_CRD = :CONTAS-CD-MDLD-CRT
                END-EXEC

                IF SQLCODE NOT EQUAL ZEROS
                   PERFORM 90070-00-MENSAGEM-ERRO-007
                END-IF
              END-IF

              MOVE GDA-CD-ANUD-PDAO           TO GDA-CD-ANUD-PDAO-I2

              EXEC SQL
                 SELECT B.QT_PCL_TIT
                      , B.QT_PCL_ADC
                 INTO   :GDA-QT-PCL-TIT-DB2
                      , :GDA-QT-PCL-ADC-DB2
                 FROM   DB2VIP.ANUD   B
                 WHERE  B.CD_ANUD         = :GDA-CD-ANUD-PDAO-I2
              END-EXEC

              IF SQLCODE NOT EQUAL ZEROS
                 PERFORM 90080-00-MENSAGEM-ERRO-008
              END-IF

              IF CONTAS-NR-SEQL-TITD-PORT EQUAL 1
                 MOVE  GDA-QT-PCL-TIT-DB2  TO GDA-QT-PCL-PDAO
              ELSE
                 MOVE  GDA-QT-PCL-ADC-DB2  TO GDA-QT-PCL-PDAO
              END-IF
           END-IF.

           SUBTRACT 1 FROM GDA-QT-PCL-PDAO.

           MOVE CONTAS-DT-INC-CBR-ANUD  TO GDA-DATA-DB2.
           MOVE GDA-DB2-DIA             TO GDA-DT-INI-CBR-DD.
           MOVE GDA-DB2-MES             TO GDA-DT-INI-CBR-MM.
           MOVE GDA-DB2-ANO             TO GDA-DT-INI-CBR-AA.

           IF (GDA-DT-INI-CBR-MM + GDA-QT-PCL-PDAO) > 12
              COMPUTE GDA-DT-FIM-CBR-MM =
                      (GDA-DT-INI-CBR-MM + GDA-QT-PCL-PDAO) - 12
              END-COMPUTE

              COMPUTE GDA-DT-FIM-CBR-AA = GDA-DT-INI-CBR-AA + 1
              END-COMPUTE
           ELSE
              COMPUTE GDA-DT-FIM-CBR-MM =
                       GDA-DT-INI-CBR-MM + GDA-QT-PCL-PDAO
              END-COMPUTE

              MOVE GDA-DT-INI-CBR-AA    TO GDA-DT-FIM-CBR-AA
           END-IF.

           MOVE GDA-DT-FIM-CBR-MM       TO IND-EH-MES

           IF EH-MES-31
              MOVE 31 TO GDA-DT-FIM-CBR-DD
           ELSE
              MOVE 30 TO GDA-DT-FIM-CBR-DD
           END-IF

           MOVE GDA-ATU-DIA             TO GDA-DT-ATU-N08-DD.
           MOVE GDA-ATU-MES             TO GDA-DT-ATU-N08-MM.
           MOVE GDA-ATU-ANO             TO GDA-DT-ATU-N08-AA.

       71000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       08000-00-OBTEM-DADOS-ANUIDADE   SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'OBTEM ANUIDADE'          TO GDA-CURSOR.

           MOVE 'N' TO WK-BB-IN-GR-158.

           PERFORM 03200-00-FILTRA-GR-ISEN-ANUD.

           MOVE CONTAS-NR-CT-CRT          TO WK-BB-NR-CT-CRT
           MOVE CONTAS-NR-SEQL-TITD-PORT  TO WK-BB-NR-SEQL-TITD-PORT.
           MOVE CONTAS-CD-SUB-MDLD-CRT    TO WK-BB-CD-SUB-MDLD-CRT

           CALL VIPP078A USING WK-PARAMETROS.

           IF IND-ERRO EQUAL ZEROS
              MOVE WK-BB-TAB-ANUIDADE  TO 140-REG-GERL
              MOVE 140-CD-ANUD         TO CONTAS-CD-ANUD
           ELSE
              DISPLAY 'Retorno VIPP0078 - ' CONTAS-NR-CT-CRT
              DISPLAY GDA-DESCRICAO-1 ' - ' GDA-LOCAL
              DISPLAY 'SQLCODE - ' GDA-081-SQLCODE
           END-IF.

           MOVE ZEROS                  TO WIND-GRMDLD.
           SET NAO-PRIVATE             TO TRUE.

           PERFORM  VARYING  WIND-GRMDLD  FROM  1  BY  1
             UNTIL  WIND-GRMDLD > 20  OR  MODALIDADE-PRIVATE
               IF TAB-CD-MDLD-CRT(WIND-GRMDLD) = CONTAS-CD-MDLD-CRT
                  SET  MODALIDADE-PRIVATE    TO TRUE
               END-IF
           END-PERFORM.

           IF MODALIDADE-PRIVATE
              PERFORM 08500-00-VERIFICA-CONVENIO
           END-IF.

           MOVE ZEROS                  TO WIND-GRMDLD.
           SET DIFERENCIADA            TO TRUE.

           PERFORM  VARYING  WIND-GRMDLD  FROM  1  BY  1
             UNTIL  WIND-GRMDLD > 20  OR  NACIONAL
               IF TAB-CD-MDLD-NAC(WIND-GRMDLD) = CONTAS-CD-MDLD-CRT
                  SET NACIONAL         TO TRUE
               END-IF
           END-PERFORM.

       08000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       03200-00-FILTRA-GR-ISEN-ANUD   SECTION.
      *----------------------------------------------------------------*  VRS115

           EXEC SQL
               SELECT 'S'
                 INTO :WK-BB-IN-GR-158
                 FROM DB2VIP.SUB_MDLD_GR
                WHERE CD_MDLD_CRT_CRD = :CONTAS-CD-MDLD-CRT
                  AND CD_SUB_MDLD_CRT = :CONTAS-CD-SUB-MDLD-CRT
                  AND CD_GR_SUB_MDLD  = 159
           END-EXEC.
      *
           IF SQLCODE NOT EQUAL 0 AND NOT EQUAL +100
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.
      *
           IF WK-BB-IN-GR-158 EQUAL 'S'
              AND CONTAS-VL-PCL-ANUD > 0
                  MOVE ZEROS TO CONTAS-NR-PCL-PND-ANUD
                  MOVE GDA-DATA-ATUAL TO CONTAS-DT-PRX-ANIV-ANUD
           END-IF.

       03200-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       08500-00-VERIFICA-CONVENIO      SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'VER CONVENIO'         TO GDA-CURSOR.

           MOVE CONTAS-NR-CT-CRT       TO 573-NR-CT-CRT.
      *                                                                   VRS115
      * ---- > Incluir pesquisa para MDLD 99 PRIVATE MASTER               VRS115
      *                                                                   VRS115
           EXEC SQL
                SELECT A.VL_PRM
                  INTO :585-VL-PRM
                  FROM DB2VIP.PRM_MDLD_PCR  A
                     , DB2VIP.CVN_PF_PCR    B
                 WHERE B.NR_CT_CRT  = :573-NR-CT-CRT
                   AND A.NR_CVN_PCR = B.NR_CVN_PCR
                   AND CD_MDLD      = :CONTAS-CD-MDLD-CRT
                   AND NM_PRM       = 'ANUIDADE'
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE NOT EQUAL +100
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              ELSE
                 GO TO 08500-99-EXIT
              END-IF
           END-IF.

      * --------- > ALTERACAO PARA PRIVATE MASTERCARD                     VRS115
           IF 585-VL-PRM  NOT EQUAL  CONTAS-CD-MDLD-CRT
              PERFORM 08600-00-OBTEM-ANUIDADE-PLABEL
              IF WRK-NR-PRIO-ANUD-CVN GREATER 140-NR-PRIO-ANUD
                 MOVE WRK-CD-ANUD-CVN      TO 140-CD-ANUD
                                              CONTAS-CD-ANUD
                 MOVE WRK-IN-CBR-PRO-RATD  TO 140-IN-CBR-PRO-RATD
                 MOVE WRK-IN-CBR-APVC-DEB  TO 140-IN-CBR-APVC-DEB
                 MOVE WRK-DT-INC-VGC       TO 140-DT-INC-VGC
                 MOVE WRK-DT-FIM-VGC       TO 140-DT-FIM-VGC
                 MOVE WRK-VL-PCL-TIT       TO 140-VL-PCL-TIT
                 MOVE WRK-VL-PCL-ADC       TO 140-VL-PCL-ADC
                 MOVE WRK-QT-PCL-TIT       TO 140-QT-PCL-TIT
                 MOVE WRK-QT-PCL-ADC       TO 140-QT-PCL-ADC
                 MOVE WRK-TX-ANUD          TO 140-TX-ANUD
                 MOVE WRK-CD-MDU-LGC       TO 140-CD-MDU-LGC
                 MOVE WRK-NR-PRIO-ANUD-CVN TO 140-NR-PRIO-ANUD
                 MOVE WRK-QT-AA-VLD-ANUD   TO 140-QT-AA-VLD-ANUD
                 MOVE WRK-QT-AA-CARE-ANUD  TO 140-QT-AA-CARE-ANUD
                 MOVE WRK-CD-NVL-ACSS      TO 140-CD-NVL-ACSS
              END-IF
           END-IF.

       08500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       08600-00-OBTEM-ANUIDADE-PLABEL  SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'ANUIDADE PLABEL'      TO GDA-CURSOR.

           MOVE  585-VL-PRM            TO WRK-CD-ANUD-CVN.

           EXEC SQL
                SELECT  IN_CBR_PRO_RATD
                     ,  IN_CBR_APVC_DEB
                     ,  DT_INC_VGC
                     ,  DT_FIM_VGC
                     ,  VL_PCL_TIT
                     ,  VL_PCL_ADC
                     ,  QT_PCL_TIT
                     ,  QT_PCL_ADC
                     ,  TX_ANUD
                     ,  CD_MDU_LGC
                     ,  NR_PRIO_ANUD
                     ,  QT_AA_VLD_ANUD
                     ,  QT_AA_CARE_ANUD
                     ,  CD_NVL_ACSS
                  INTO  :WRK-IN-CBR-PRO-RATD
                     ,  :WRK-IN-CBR-APVC-DEB
                     ,  :WRK-DT-INC-VGC
                     ,  :WRK-DT-FIM-VGC
                     ,  :WRK-VL-PCL-TIT
                     ,  :WRK-VL-PCL-ADC
                     ,  :WRK-QT-PCL-TIT
                     ,  :WRK-QT-PCL-ADC
                     ,  :WRK-TX-ANUD
                     ,  :WRK-CD-MDU-LGC:WS-BB-NOT-NULL-CD-MDU
                     ,  :WRK-NR-PRIO-ANUD-CVN:WS-BB-NOT-NULL-NR-PRIO
                     ,  :WRK-QT-AA-VLD-ANUD:WS-BB-NOT-NULL-VLD-AN
                     ,  :WRK-QT-AA-CARE-ANUD:WS-BB-NOT-NULL-CAR-AN
                     ,  :WRK-CD-NVL-ACSS:WS-BB-NOT-NULL-NVL-ACSS
                  FROM  DB2VIP.ANUD
                 WHERE  CD_ANUD  =  :WRK-CD-ANUD-CVN
           END-EXEC.

           IF  WS-BB-NOT-NULL-CD-MDU   IS LESS THAN  ZEROS
               MOVE  ZEROS             TO  WRK-CD-MDU-LGC
           END-IF.

           IF  WS-BB-NOT-NULL-NR-PRIO  IS LESS THAN  ZEROS
               MOVE  ZEROS             TO  WRK-NR-PRIO-ANUD-CVN
           END-IF.

           IF  WS-BB-NOT-NULL-VLD-AN   IS LESS THAN  ZEROS
               MOVE  ZEROS             TO  WRK-QT-AA-VLD-ANUD
           END-IF.

           IF  WS-BB-NOT-NULL-CAR-AN   IS LESS THAN  ZEROS
               MOVE  ZEROS             TO  WRK-QT-AA-CARE-ANUD
           END-IF.

           IF  WS-BB-NOT-NULL-NVL-ACSS IS LESS THAN  ZEROS
               MOVE  ZEROS             TO  WRK-CD-NVL-ACSS
           END-IF.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

       08600-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       10000-00-ATUALIZA-CARENCIA      SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'ATUAL. CARENCIA'      TO GDA-CURSOR.

           MOVE GDA-ATU-DIA            TO GDA-SBC-DIA
           MOVE GDA-ATU-MES            TO GDA-SBC-MES
           MOVE GDA-ATU-ANO            TO GDA-SBC-ANO
           MOVE GDA-SBC-DATA           TO ARG01-13.

           COMPUTE QTD-DIAS-CORR = 140-QT-AA-CARE-ANUD * 30.

           CALL SBDATA USING FUNCAO-13 ARG01-13 ARG02-13 ARG03-13.

           IF ARG01-13 EQUAL 99999999 OR
              ARG02-13 EQUAL 88888888
              PERFORM 90030-00-MENSAGEM-ERRO-003
           END-IF.

           MOVE ARG02-13               TO GDA-SBC-DATA
           MOVE GDA-SBC-DIA            TO GDA-DB2-DIA
           MOVE GDA-SBC-MES            TO GDA-DB2-MES
           MOVE GDA-SBC-ANO            TO GDA-DB2-ANO
           MOVE GDA-DATA-DB2           TO CONTAS-DT-PRX-ANIV-ANUD.

           MOVE 'GRAVA PORTADOR'       TO GDA-CURSOR.

           EXEC SQL
                UPDATE DB2VIP.PORT_CRT
                   SET DT_PRX_ANIV_ANUD  = :CONTAS-DT-PRX-ANIV-ANUD
                     , DT_INC_CBR_ANUD   = :GDA-DATA-ATUAL
                     , CD_ANUD           = :CONTAS-CD-ANUD
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                   AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

           MOVE 'GRAVA ANUIDADE'       TO GDA-CURSOR.


           EXEC SQL
                UPDATE DB2VIP.ANUD_PORT
                   SET QT_AA_CARE_ANUD   = 0
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                   AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE NOT EQUAL +100
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF
           END-IF.

       10000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       11000-00-OBTEM-TITULAR          SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'OBTEM TITULAR'        TO GDA-CURSOR.

           MOVE SPACES                 TO GDA-TIT-NAO-ATIVADO.

           EXEC SQL
                SELECT DT_PRX_ANIV_ANUD
                     , DT_INC_CBR_ANUD
                     , DT_PRMO_CBR_ANUD
                     , CD_TIP_CBR_ANUD
                     , IN_CBR_ANUD
                  INTO :GDA-DTA-ANI-TIT
                     , :GDA-DTA-INC-CBR-ANUD
                     , :GDA-DTA-PRIME-CBR-ANUD
                     , :GDA-INDICADOR-CBR
                     , :GDA-IN-CBR
                  FROM DB2VIP.PORT_CRT
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                   AND CD_TITD_PORT      = 1
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE EQUAL +100
                 DISPLAY 'Conta sem titular ' CONTAS-NR-CT-CRT
              ELSE
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF
           ELSE
              IF (GDA-DTA-ANI-TIT          LESS   GDA-AMD-FINAL  AND
                  GDA-DTA-PRIME-CBR-ANUD   EQUAL  '01.01.0001'   AND
                  GDA-DTA-INC-CBR-ANUD     EQUAL  '01.01.0001')
              OR (GDA-INDICADOR-CBR        EQUAL  1)
                  MOVE '*'             TO GDA-TIT-NAO-ATIVADO
              END-IF
           END-IF.

       11000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       12000-00-CALCULA-ANUIDADE       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'CALC.ANUIDADE'        TO GDA-CURSOR.
      *                                                                   VRS115
           PERFORM 15100-01-VERIFICA-DSC-SUB.
           IF CONTAS-NR-PCL-PND-ANUD EQUAL ZEROS
              IF 140-IN-CBR-PRO-RATD EQUAL 'S'
                 IF CONTAS-CD-TITD-PORT NOT EQUAL 1
                    PERFORM 18000-00-CALCULA-DIF-DATAS
                    IF WPRORAT-DIF-DATAS NOT LESS 12
                       MOVE GDA-DTA-ANI-TIT  TO CONTAS-DT-PRX-ANIV-ANUD
                       IF IND-DSC-SUB = 'N'
                          PERFORM 15000-00-CALCULA-PRIMEIRA
                       ELSE
                          PERFORM 15000-00-CALC-PRIM-SUB
                       END-IF
                    ELSE
                       IF IND-DSC-SUB = 'N'
                          PERFORM 16000-00-CALCULA-PRO-RATA
                       ELSE
                          PERFORM 16000-00-CALC-PRORATA-SUB
                       END-IF
                    END-IF
003948           ELSE
                    IF IND-DSC-SUB = 'N'
                       PERFORM 15000-00-CALCULA-PRIMEIRA
                    ELSE
                       PERFORM 15000-00-CALC-PRIM-SUB
                    END-IF
                 END-IF
              ELSE
                 IF IND-DSC-SUB = 'N'
                    PERFORM 15000-00-CALCULA-PRIMEIRA
                 ELSE
                    PERFORM 15000-00-CALC-PRIM-SUB
                 END-IF
              END-IF
           ELSE
              MOVE CONTAS-VL-PCL-ANUD  TO GDA-VL-ANUD
           END-IF.
       12000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       13000-00-ATUALIZA-TABS          SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE ZEROS TO GDA-VL-ANUD-CBR-PORT
                         GDA-VL-DSC-PORT.

           MOVE 'UPDATE TABS'          TO GDA-CURSOR.
      * início de um novo ciclo de anuidade
           IF CONTAS-NR-PCL-PND-ANUD EQUAL ZEROS
              MOVE 'UPDATE PORT_CR'    TO GDA-CURSOR
              MOVE CONTAS-DT-PRX-ANIV-ANUD TO GDA-DATA-DB2
              IF GDA-DB2-MES = 2
                 IF GDA-DB2-DIA GREATER 28
                    MOVE 28            TO GDA-DB2-DIA
                 END-IF
              END-IF
              MOVE GDA-DB2-DIA         TO GDA-DIA-ANI
              MOVE GDA-DB2-MES         TO GDA-MES-ANI
              MOVE GDA-DB2-ANO         TO GDA-ANO-ANI
     *** IF abaixo sera sempre satisfeito
              IF GDA-DATA-ANI-INVER NOT GREATER GDA-AMD-FINAL
      *** ********************************************************* ***   VRS115
      *** Rotina SBDATA tem limitacao para calculo entre datas em   ***   VRS115
      ***      que o retorno seja superior a determinado valor.     ***   VRS115
      *** ********************************************************* ***   VRS115
                 IF GDA-DATA-ANI-INVER LESS 19990101
                    MOVE GDA-DATA-ATUAL   TO GDA-DATA-DB2
                 ELSE
                    PERFORM 17000-00-ATUALIZA-ANO
                 END-IF
                 IF GDA-DB2-MES = 2
                    IF GDA-DB2-DIA GREATER 28
                       MOVE 28            TO GDA-DB2-DIA
                    END-IF
                 END-IF
                 ADD 1                    TO GDA-DB2-ANO
              END-IF
              MOVE GDA-DATA-DB2        TO CONTAS-DT-PRX-ANIV-ANUD
              IF CONTAS-CD-TITD-PORT EQUAL 1
      ***        MOVE GDA-VL-PCL-TIT   TO CONTAS-VL-PCL-ANUD              VRS115
                 MOVE 140-VL-PCL-TIT   TO CONTAS-VL-PCL-ANUD
                 MOVE GDA-QT-PCL-TIT   TO CONTAS-QT-TTL-PCL-ANUD
                 COMPUTE CONTAS-NR-PCL-PND-ANUD = GDA-QT-PCL-TIT - 1
              ELSE
      ***        MOVE GDA-VL-PCL-ADC   TO CONTAS-VL-PCL-ANUD              VRS115
                 MOVE 140-VL-PCL-ADC   TO CONTAS-VL-PCL-ANUD
                 MOVE GDA-QT-PCL-ADC   TO CONTAS-QT-TTL-PCL-ANUD
                 COMPUTE CONTAS-NR-PCL-PND-ANUD = GDA-QT-PCL-ADC - 1
              END-IF
              IF CONTAS-DT-PRMO-CBR-ANUD EQUAL '01.01.0001'  AND
                 CONTAS-DT-INC-CBR-ANUD  EQUAL '01.01.0001'
                 MOVE GDA-DATA-ATUAL   TO CONTAS-DT-PRMO-CBR-ANUD
              END-IF
              EXEC SQL
                   UPDATE DB2VIP.PORT_CRT
                      SET DT_PRX_ANIV_ANUD  = :CONTAS-DT-PRX-ANIV-ANUD
                        , CD_ANUD           = :CONTAS-CD-ANUD
      ***                 CD_TIP_CBR_ANUD   = :GDA-CD-TIP-CBR-ANUD,       VRS115
      ***                 IN_CBR_ANUD       = :GDA-IN-CBR-ANUD,           VRS115
                        , DT_INC_CBR_ANUD   = :GDA-DATA-ATUAL
                        , DT_PRMO_CBR_ANUD  = :CONTAS-DT-PRMO-CBR-ANUD
                        , VL_PCL_ANUD       = :CONTAS-VL-PCL-ANUD
                        , NR_PCL_PND_ANUD   = :CONTAS-NR-PCL-PND-ANUD
                        , QT_TTL_PCL_ANUD   = :CONTAS-QT-TTL-PCL-ANUD
                        , VL_ANUD_FATD      = :CONTAS-VL-PCL-ANUD
                    WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                      AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
              END-EXEC
              IF SQLCODE NOT EQUAL ZEROS
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF
           ELSE
      * continuação de um ciclo de anuidade já iniciado previamente
              IF (CONTAS-CD-MDLD-CRT EQUAL 03 OR 07 OR 31 OR 32
                  OR 33 OR 34 OR 41 OR 42 OR 43 OR 56 OR 57 OR 58
                  OR 71 OR 82 OR 95 OR 96 OR 114 OR 185 OR 186
                  OR 97 OR 191 OR 197)
                 IF CONTAS-CD-TITD-PORT EQUAL 1
                    MOVE GDA-VL-PCL-TIT   TO CONTAS-VL-PCL-ANUD
                 ELSE
                    MOVE GDA-VL-PCL-ADC   TO CONTAS-VL-PCL-ANUD
                 END-IF
              END-IF

              COMPUTE CONTAS-NR-PCL-PND-ANUD = CONTAS-NR-PCL-PND-ANUD
                                               - 1

              EXEC SQL
                   UPDATE DB2VIP.PORT_CRT
                      SET NR_PCL_PND_ANUD   = :CONTAS-NR-PCL-PND-ANUD,
                          VL_ANUD_FATD      = VL_ANUD_FATD
                                            + :CONTAS-VL-PCL-ANUD
                    WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                      AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
              END-EXEC
              IF SQLCODE NOT EQUAL ZEROS
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF
           END-IF.

           IF CONTAS-VL-PCL-ANUD GREATER ZEROS
      *                                                                   VRS115
              IF CONTAS-NR-PLST EQUAL ZEROS
                 PERFORM 14100-00-OBTEM-PLASTICO
              ELSE
                 PERFORM 14200-00-OBTEM-PLASTICO-BOM
              END-IF
      *                                                                   VRS115
              PERFORM 14000-00-GRAVA-MOVTO
      *
      * MOCK-POINT FORCA-ERRO-010
      *
              IF WK-BB-CODIGO-OCI NOT EQUAL ZEROS
                 PERFORM 24000-00-DESCONTO-OCI
              ELSE                                                        VRS119
                 PERFORM 271000-00-CALCULA-DESCONTOS
              END-IF

      *                                                                   VRS115
           END-IF.
      **                                                                  VRS115
      ** Grava registro de portadores no periodo de cobranca de anuidade  VRS115
      ** Tipo de registro F007-TIP-REG:                                   VRS115
      ** "A" - Portadores no inicio do periodo de cobranca (cobrados e    VRS115
      **       portadores isentos )                                       VRS115
      ** "B" - Portadores durante o periodo de cobranca (cobrados)        VRS115
      ** "C" - Portadores durante o periodo de cobranca (isentos)         VRS115
      ** ---------------------------------------------------------------  VRS115
           MOVE CONTAS-NR-CT-CRT     TO F007-NR-CT-CRT.
           MOVE CONTAS-NR-SEQL-TITD-PORT
                                     TO F007-NR-SEQL-TITD-PORT.
           MOVE GDA-VL-ANUD-CBR-PORT TO F007-VL-ANUD-CBR.
           MOVE GDA-VL-DSC-PORT      TO F007-VL-DSC-ANUD.
           MOVE GDA-DATA-ATUAL       TO F007-DT-MVT-ANUD.
           WRITE FD-REG-VIPF007.
           ADD 1 TO CNT-REG-VIPF007.

       13000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       14000-00-GRAVA-MOVTO            SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'INSERT MOVTO'         TO GDA-CURSOR.

           COMPUTE GDA-PARCELA = CONTAS-QT-TTL-PCL-ANUD -
                                 CONTAS-NR-PCL-PND-ANUD.

           MOVE SPACES                 TO WDESCRICAO
           MOVE GDA-PARCELA            TO WPARC-PEND
           MOVE CONTAS-QT-TTL-PCL-ANUD TO WPARC-TOTAL.


           IF NACIONAL
              MOVE 'NACIONAL    '   TO DESC-ANUID
           ELSE
              MOVE 'DIFERENCIADA'   TO DESC-ANUID
           END-IF

      *
      * MOCK-POINT FORCA-ERRO-005
      *
           IF CONTAS-CD-TITD-PORT EQUAL 1
              STRING 'ANUIDADE ' DESC-ANUID ' TIT-PARC ' WPARC-PEND
                      DELIMITED BY SIZE
                      '/' WPARC-TOTAL
                      DELIMITED BY SIZE     INTO WDESCRICAO
           ELSE
              IF WS-PRORATA EQUAL 'S'
                 MOVE SPACES           TO WS-PRORATA
                 STRING 'ANUD. ' DESC-ANUID ' PRORATA ADC ' WPARC-PEND    VRS133
                         DELIMITED BY SIZE
                         '/' WPARC-TOTAL
                         DELIMITED BY SIZE     INTO WDESCRICAO
              ELSE
                 STRING 'ANUIDADE ' DESC-ANUID ' ADC-PARC ' WPARC-PEND
                         DELIMITED BY SIZE
                         '/' WPARC-TOTAL
                         DELIMITED BY SIZE     INTO WDESCRICAO
              END-IF
           END-IF.

           MOVE SPACES                 TO LK82-PARAMETROS
                                          LK82-RETORNO.
           MOVE CONTAS-NR-CT-CRT       TO LK82-NR-CT-CRT
                                          LK82-NR-CTL-SSIS-OGM.
           MOVE CONTAS-NR-PLST         TO LK82-NR-PLST.
           MOVE GDA-DATA-ATUAL         TO LK82-DT-EFT-TRAN
                                          LK82-DT-MVT-CT-CRT.
           MOVE WDESCRICAO             TO LK82-TX-MVT-CT-CRT.
      *****************************************************************   VRS115
      ***  Atencao: O valor do movimento de anuidade eh gravado a   ***   VRS115
      ***           da variavel CONTAS-VL-PCL-ANUD                  ***   VRS115
      *****************************************************************   VRS115
           MOVE CONTAS-VL-PCL-ANUD     TO LK82-VL-MOE-OGNL-MVT
                                          GDA-VL-ANUD-CBR-PORT
                                          LK82-VL-MVT-CT-CRT.
           MOVE 21                     TO LK82-CD-PLN-VIP.
           MOVE 'ANU'                  TO LK82-SG-SSIS-OGM.
           MOVE 603000                 TO LK82-CD-TRAN.
           MOVE 1001                   TO LK82-CD-DET-TRAN.
           MOVE '2'                    TO LK82-IN-PSTG.
           MOVE '986'                  TO LK82-CD-MOE-OGNL.
           MOVE 100                    TO LK82-CD-ORG.
           MOVE SPACES                 TO LK82-CD-AUTZ-TRAN
                                          LK82-CD-MDU-PRCR
                                          LK82-CD-ITCB-CRT.
           MOVE 'VIPP0007'             TO LK82-CD-USU-RSP-LCTO.
           MOVE CONTAS-CD-MDLD-CRT     TO LK82-NR-TIP-MDLD.
           MOVE ZEROS                  TO LK82-NR-CMPT-PLST
                                          LK82-VL-US-MVT-CT-CRT
                                          LK82-NR-CTR-NEGO
                                          LK82-NR-TIP-PROD
                                          LK82-NR-CD-DEPE
                                          LK82-IND-ERRO
                                          LK82-EIBRESP
                                          LK82-NR-PCL-MVT-CPR
                                          LK82-QT-PCL-MVT-CPR
                                          LK82-VL-CNV-DT-CPR
                                          LK82-NR-IDFR-TRAN-C.
           MOVE 'S'                    TO LK82-IND-TIPO-COMP.

           PERFORM 14600-00-BUSCA-REFNUMBER.

           CALL VIPP0082 USING LK82-MVT-PARAM.

           IF  LK82-IND-ERRO NOT EQUAL ZEROS
               DISPLAY LK82-RETORNO
               DISPLAY LK82-DESCRICAO-1
               DISPLAY LK82-DESCRICAO-2
               DISPLAY LK82-SQLCODE
               DISPLAY LK82-SQLCODE-COMP
               MOVE LK82-SQLCODE       TO GDA-CODESQL
                                          SQLCODE
               DISPLAY 'Erro Programa VIPP0082 - ' GDA-CODESQL
               PERFORM 90010-00-MENSAGEM-ERRO-001.
      * botar END-IF  <<<
           ADD 1                       TO WCOMMIT
                                          WGRAVADOS.

           IF  WCOMMIT GREATER 10
               MOVE GDA-DATA-VIP7      TO 207-VL-TIP-DT
               MOVE GDA-CTRL-CICLO     TO 207-QT-DCML
               PERFORM 14500-00-ATUALIZA-LIDER
               MOVE 'COMMIT PARCIAL'   TO GDA-CURSOR
               EXEC SQL
                    COMMIT
               END-EXEC
               IF SQLCODE NOT EQUAL ZEROS
                  PERFORM 90010-00-MENSAGEM-ERRO-001
               END-IF
               MOVE ZEROS              TO WCOMMIT
           END-IF.

           PERFORM 290000-00-GRAVA-MVT-ANUD.

       14000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       14000-02-CALCULA-DAA            SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           MOVE 'CALCULA-DAA' TO GDA-CURSOR.
      *                                                                   VRS115
           INITIALIZE  PARM-VIPP4848.

           MOVE CONTAS-CD-CLI            TO 048W-CD-CLI.
           MOVE CONTAS-NR-CT-CRT         TO 048W-NR-CT-CRT.
           MOVE CONTAS-CD-MDLD-CRT       TO 048W-CD-MDLD-CRT.
           MOVE GDA-SUB-MDLD             TO 048W-CD-SUB-MDLD.
           MOVE CONTAS-NR-SEQL-TITD-PORT TO 048W-NR-SEQL-TITD.
           MOVE GDA-VL-ANUD              TO 048W-VL-PCL-ANUD.
      *                                                                   VRS115
           MOVE LENGTH OF PARM-VIPP4848 TO EIBCALEN.
           CALL VIPP4848 USING DFHEIBLK PARM-VIPP4848.
      *                                                                   VRS115
       14000-99-EXIT.
           EXIT.
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
       14000-02-GRAVA-MOVTO-DAA        SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'INSERT MOVTO-DAA'      TO GDA-CURSOR.
      *                                                                   VRS115
           COMPUTE GDA-PARCELA = CONTAS-QT-TTL-PCL-ANUD -
                                 CONTAS-NR-PCL-PND-ANUD.

           MOVE SPACES                 TO WDESCRICAO
           MOVE GDA-PARCELA            TO WPARC-PEND
           MOVE CONTAS-QT-TTL-PCL-ANUD TO WPARC-TOTAL.

           IF CONTAS-CD-TITD-PORT EQUAL 1
              STRING 'DESC AUTOMATICO ANUD. TIT-PARC '                    VRS133
              WPARC-PEND DELIMITED BY SIZE
                      '/' WPARC-TOTAL
                      DELIMITED BY SIZE     INTO WDESCRICAO
           ELSE
              IF WS-PRORATA EQUAL 'S'
                 MOVE SPACES           TO WS-PRORATA
                 STRING 'DESC AUTOMAT. ANUD PRORATA ADC '                 VRS133
                 WPARC-PEND DELIMITED BY SIZE
                         '/' WPARC-TOTAL
                         DELIMITED BY SIZE     INTO WDESCRICAO
              ELSE
                 STRING 'DESC AUTOMATICO ANUID ADC-PARC '                 VRS133
                 WPARC-PEND DELIMITED BY SIZE
                         '/' WPARC-TOTAL
                         DELIMITED BY SIZE     INTO WDESCRICAO
              END-IF
           END-IF.

           MOVE SPACES                 TO LK82-PARAMETROS
                                          LK82-RETORNO.
           MOVE CONTAS-NR-CT-CRT       TO LK82-NR-CT-CRT
                                          LK82-NR-CTL-SSIS-OGM.
           MOVE CONTAS-NR-PLST         TO LK82-NR-PLST.
           MOVE GDA-DATA-ATUAL         TO LK82-DT-EFT-TRAN
                                          LK82-DT-MVT-CT-CRT.
           MOVE WDESCRICAO             TO LK82-TX-MVT-CT-CRT.
      *****************************************************************   VRS115
      ***  Atencao: O valor do movimento de anuidade eh gravado a   ***   VRS115
      ***           da variavel CONTAS-VL-PCL-ANUD                  ***   VRS115
      *****************************************************************   VRS115
           MOVE GDA-VL-ESTN-DAA        TO LK82-VL-MOE-OGNL-MVT
                                          GDA-VL-DSC-PORT
                                          LK82-VL-MVT-CT-CRT.
           MOVE 21                     TO LK82-CD-PLN-VIP.
           MOVE 'ANU'                  TO LK82-SG-SSIS-OGM.
           MOVE 613000                 TO LK82-CD-TRAN.
           MOVE 1001                   TO LK82-CD-DET-TRAN.
           MOVE '2'                    TO LK82-IN-PSTG.
           MOVE '986'                  TO LK82-CD-MOE-OGNL.
           MOVE 100                    TO LK82-CD-ORG.
           MOVE SPACES                 TO LK82-CD-AUTZ-TRAN
                                          LK82-CD-MDU-PRCR
                                          LK82-CD-ITCB-CRT.
           MOVE 'VIPP0007'             TO LK82-CD-USU-RSP-LCTO.
           MOVE CONTAS-CD-MDLD-CRT     TO LK82-NR-TIP-MDLD.
           MOVE ZEROS                  TO LK82-NR-CMPT-PLST
                                          LK82-VL-US-MVT-CT-CRT
                                          LK82-NR-CTR-NEGO
                                          LK82-NR-TIP-PROD
                                          LK82-NR-CD-DEPE
                                          LK82-IND-ERRO
                                          LK82-EIBRESP
                                          LK82-NR-PCL-MVT-CPR
                                          LK82-QT-PCL-MVT-CPR
                                          LK82-VL-CNV-DT-CPR
                                          LK82-NR-IDFR-TRAN-C.
           MOVE 'S'                    TO LK82-IND-TIPO-COMP.

           PERFORM 14600-00-BUSCA-REFNUMBER.

           CALL VIPP0082 USING LK82-MVT-PARAM.

           IF  LK82-IND-ERRO NOT EQUAL ZEROS
               DISPLAY LK82-RETORNO
               DISPLAY LK82-DESCRICAO-1
               DISPLAY LK82-DESCRICAO-2
               DISPLAY LK82-SQLCODE
               DISPLAY LK82-SQLCODE-COMP
               MOVE LK82-SQLCODE       TO GDA-CODESQL
                                          SQLCODE
               DISPLAY 'Erro Programa VIPP0082 - ' GDA-CODESQL
               PERFORM 90010-00-MENSAGEM-ERRO-001.

           ADD 1                       TO WCOMMIT
                                          WGRAVADOS.

           IF  WCOMMIT GREATER 10
               MOVE GDA-DATA-VIP7      TO 207-VL-TIP-DT
               MOVE GDA-CTRL-CICLO     TO 207-QT-DCML
               PERFORM 14500-00-ATUALIZA-LIDER
               MOVE 'COMMIT PARCIAL'   TO GDA-CURSOR
               EXEC SQL
                    COMMIT
               END-EXEC
               IF SQLCODE NOT EQUAL ZEROS
                  PERFORM 90010-00-MENSAGEM-ERRO-001
               END-IF
               MOVE ZEROS              TO WCOMMIT
           END-IF.

           PERFORM 290000-00-GRAVA-MVT-ANUD.
           PERFORM 14000-02-INSERT-TAB-DAA.
      *                                                                   VRS115
           EXEC SQL
                UPDATE DB2VIP.PORT_CRT
                   SET VL_ANUD_FATD      = VL_ANUD_FATD
                                         - :GDA-VL-ESTN-DAA
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                   AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.
      *                                                                   VRS115
           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.
      *                                                                   VRS115
       14000-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       14000-02-INSERT-TAB-DAA         SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           INITIALIZE  PARM-VIPP4854.
           MOVE CONTAS-NR-CT-CRT         TO  0485W-NR-CT-CRT.
           MOVE CONTAS-NR-SEQL-TITD-PORT TO  0485W-NR-SEQL-TITD.
           MOVE GDA-VL-ESTN-DAA          TO  0485W-VL-DSC-AUTC-ANUD.
           MOVE WPARC-PEND               TO  0485W-NR-PCL-DSC-AUTC-ANUD.
           MOVE CONTAS-CD-ANUD           TO  0485W-CD-ANUD.
           MOVE KS958-OUTPUT-REF-NUM     TO  0485W-NR-REF-TRAN.
      *                                                                   VRS115
           MOVE LENGTH OF PARM-VIPP4854 TO EIBCALEN.
           CALL VIPP4854 USING DFHEIBLK PARM-VIPP4854.
      *                                                                   VRS115
           IF 0485W-MSG-ERRO NOT EQUAL ' '
              DISPLAY '*** Ocorreu erro no pgm: VIPP4854 = '
              0485W-MSG-ERRO UPON SYSOUT
              DISPLAY 'SQLCODE : ' 0485W-SQL-CODE UPON SYSOUT
           END-IF.
      *                                                                   VRS115
       14000-99-EXIT.
           EXIT.
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
       14100-00-OBTEM-PLASTICO         SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE  'OBTEM PLASTICO'      TO GDA-CURSOR.

      *     MOVE  'VIPP0007'            TO WS-ABEND-PROG-ID               VRS115

           EXEC  SQL
                 SELECT NR_PLST
                      , CD_TIP_RST_CRT_CRD
                   INTO :CONTAS-NR-PLST
                      , :GDA-CD-TIP-RST-PLST
                   FROM DB2VIP.PLST_PORT
                  WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                    AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.

           IF  SQLCODE NOT EQUAL ZEROS AND -811 AND +100
               PERFORM 90010-00-MENSAGEM-ERRO-001
           ELSE
               IF SQLCODE EQUAL -811 OR +100
                  MOVE ZEROS           TO CONTAS-NR-PLST
                                          GDA-CD-TIP-RST-PLST
               END-IF
           END-IF.

           IF  GDA-CD-TIP-RST-PLST  NOT EQUAL  ZEROS
               MOVE ZEROS              TO CONTAS-NR-PLST
           END-IF.

       14100-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       14200-00-OBTEM-PLASTICO-BOM     SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE  'OBTEM PLASTICO BOM'  TO GDA-CURSOR.

      *     MOVE  'VIPP0007'            TO WS-ABEND-PROG-ID               VRS115

           EXEC  SQL
                 SELECT CD_TIP_RST_CRT_CRD
                   INTO :GDA-CD-TIP-RST-PLST
                   FROM DB2VIP.PLST_PORT
                  WHERE NR_PLST           = :CONTAS-NR-PLST
           END-EXEC.

           IF  SQLCODE NOT EQUAL ZEROS AND -811 AND +100
               PERFORM 90010-00-MENSAGEM-ERRO-001
           ELSE
               IF SQLCODE EQUAL -811 OR +100
                  MOVE ZEROS           TO CONTAS-NR-PLST
                                          GDA-CD-TIP-RST-PLST
               END-IF
           END-IF.

           IF  GDA-CD-TIP-RST-PLST  NOT EQUAL  ZEROS
               MOVE ZEROS              TO CONTAS-NR-PLST
           END-IF.

       14200-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       14500-00-ATUALIZA-LIDER         SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE  'ATUALIZA LIDER'      TO GDA-CURSOR.

      *     MOVE  'VIPP0007'            TO WS-ABEND-PROG-ID               VRS115
           MOVE  'VIP'                 TO 207-CD-SIST
           MOVE  'VIPP0007'            TO 207-NM-PRM
           MOVE  CONTAS-NR-CT-CRT      TO 207-VL-TIP-NR.

           EXEC  SQL
                 UPDATE DB2VIP.LIDER
                    SET VL_TIP_NR = :207-VL-TIP-NR,
                        VL_TIP_DT = :207-VL-TIP-DT,
                        QT_DCML   = :207-QT-DCML
                  WHERE CD_SIST = :207-CD-SIST  AND
                        NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF  SQLCODE NOT EQUAL ZEROS
               PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

       14500-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       14600-00-BUSCA-REFNUMBER        SECTION.
      *----------------------------------------------------------------*  VRS115
           INITIALIZE  VIPKS957.
      *                                                                   VRS115
           MOVE  01                    TO  KS957-INPUT-CD-FUC.
           MOVE  CONTAS-NR-CT-CRT      TO  KS957-NR-CT-CRT-F01.
      *                                                                   VRS115
           MOVE  ZEROS                 TO  KS957-COD-RET
                                           KS957-SQLCODE.
      *
           MOVE LENGTH OF WS-VIPKS957 TO EIBCALEN.
           CALL  VIPSB957  USING  DFHEIBLK
                                  WS-VIPKS957
           END-CALL.
      *
      * MOCK-POINT FORCA-ERRO-001
      *
           IF  KS957-COD-RET NOT = ZEROS
               PERFORM  999015-ERRO-15
           END-IF.

           INITIALIZE VIPKS958.

           MOVE 'ANU'                  TO KS958-INPUT-SGL-SIS.
           MOVE KS957-CD-PRF-AG-RLC-S1 TO KS958-INPUT-PRF-AGE
                                          LK82-NR-CD-DEPE.
           ADD  1                      TO GDA-SEQL-REFNUM.
           MOVE GDA-SEQL-REFNUM        TO KS958-INPUT-NRO-SQL.

           MOVE LENGTH OF WS-VIPKS958 TO EIBCALEN.
           CALL  VIPSB958      USING  DFHEIBLK
                                      WS-VIPKS958
           END-CALL.

      *
      * MOCK-POINT FORCA-ERRO-002
      *

           IF  KS958-COD-RET NOT = ZEROS
               PERFORM  999016-ERRO-16
           ELSE
               MOVE KS958-OUTPUT-REF-NUM TO LK82-CD-MDU-PRCR
           END-IF.
      *                                                                   VRS115
           MOVE 'N'                    TO LK82-IN-MVT-CTB.
      *                                                                   VRS115
       14600-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS122
       14700-00-BUSCA-GSTO             SECTION.                           VRS122
      *----------------------------------------------------------------*  VRS122
           MOVE 'BUSCA-GSTO' TO GDA-CURSOR.                               VRS122
      *
           INITIALIZE  PARM-VIPP4865.                                     VRS122
      *
           MOVE CONTAS-NR-CT-CRT       TO VIPK4865-NR-CT-CRT              VRS122
           MOVE CONTAS-CD-MDLD-CRT     TO VIPK4865-CD-MDLD-CRT            VRS122
           MOVE GDA-SUB-MDLD           TO VIPK4865-CD-SUB-MDLD            VRS122
           MOVE GDA-VL-ANUD            TO VIPK4865-VL-PCL-ANUD            VRS122
      *
           MOVE LENGTH OF PARM-VIPP4865 TO EIBCALEN                       VRS122
           CALL VIPP4865 USING DFHEIBLK PARM-VIPP4865                     VRS122
      *
           .
       14700-99-EXIT.                                                     VRS122
           EXIT.                                                          VRS122

      *----------------------------------------------------------------*  VRS123
       15100-01-VERIFICA-DSC-SUB       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'N'                         TO IND-DSC-SUB

           IF CONTAS-CD-SUB-MDLD-CRT = 0
              MOVE CONTAS-NR-CT-CRT         TO 101-NR-CT-CRT
              MOVE CONTAS-CD-MDLD-CRT       TO 101-CD-MDLD-CRT
              MOVE 1                        TO 103-NR-SEQL-TITD-PORT
              EXEC SQL
                   SELECT CD_SUB_MDLD_PLST
                     INTO :103-CD-SUB-MDLD-PLST
                     FROM DB2VIP.CT_CRT    A
                        , DB2VIP.PLST_PORT B
                    WHERE A.NR_CT_CRT         = :101-NR-CT-CRT
                      AND A.CD_MDLD_CRT       = :101-CD-MDLD-CRT
                      AND B.NR_SEQL_TITD_PORT = :103-NR-SEQL-TITD-PORT
                      AND B.NR_CT_CRT         = A.NR_CT_CRT
                      AND B.CD_CLI_PORT       = A.CD_CLI
                    FETCH FIRST 1 ROW ONLY
              END-EXEC
              IF SQLCODE NOT EQUAL ZEROS
                 MOVE 'N'                   TO IND-DSC-SUB
              ELSE
                 MOVE 103-CD-SUB-MDLD-PLST  TO GDA-CD-SUB-MDLD-CRT
                 PERFORM 15101-01-ACIONA-VIPST752
              END-IF
           ELSE
              MOVE CONTAS-CD-SUB-MDLD-CRT   TO GDA-CD-SUB-MDLD-CRT
                 PERFORM 15101-01-ACIONA-VIPST752
           END-IF.

       15100-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       15101-01-ACIONA-VIPST752        SECTION.
      *----------------------------------------------------------------*  VRS115
           INITIALIZE PARM-VIPST752.
      *                                                                   VRS115
           MOVE 4                           TO KT752-CD-FUC
           MOVE GDA-CD-MDLD-CRT-CRD         TO KT752-CD-MDLD-CRT-CRD
           MOVE GDA-CD-SUB-MDLD-CRT         TO KT752-CD-SUB-MDLD-CRT
           MOVE 109                         TO KT752-CD-GR-SUB-MDLD
      *                                                                   VRS115
           MOVE LENGTH OF PARM-VIPST752 TO EIBCALEN.
           CALL  VIPST752 USING DFHEIBLK PARM-VIPST752

           IF KT752-CD-ERRO NOT = ZEROS
              MOVE 'N'                      TO IND-DSC-SUB
           ELSE
              MOVE KT752-IND-ANUD           TO IND-DSC-SUB
           END-IF.
       15101-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       15102-01-VIPST752-GR107        SECTION.
      *----------------------------------------------------------------*  VRS115
           INITIALIZE PARM-VIPST752.
      *                                                                   VRS115
           MOVE 4                           TO KT752-CD-FUC
           MOVE GDA-CD-MDLD-CRT-CRD         TO KT752-CD-MDLD-CRT-CRD
           MOVE GDA-CD-SUB-MDLD-CRT         TO KT752-CD-SUB-MDLD-CRT
           MOVE 107                         TO KT752-CD-GR-SUB-MDLD
      *                                                                   VRS115
           MOVE LENGTH OF PARM-VIPST752 TO EIBCALEN.
           CALL  VIPST752 USING DFHEIBLK PARM-VIPST752

           IF KT752-CD-ERRO NOT = ZEROS
              MOVE 'N'                      TO IND-DSC-SUB
           ELSE
              MOVE KT752-IND-ANUD           TO IND-DSC-SUB
           END-IF.
       15101-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       15000-00-CALCULA-PRIMEIRA       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'CALC. PRIMEIRA'       TO GDA-CURSOR.
      *                                                                   VRS115
           PERFORM 18500-00-VERIFICA-DESCONTO.
      *                                                                   VRS115
           IF GDA-IDENT-DSC EQUAL 'S'
              PERFORM 19000-00-CALC-DESCONTOS

              IF CONTAS-CD-TITD-PORT EQUAL 1
                 MOVE 140-QT-PCL-TIT   TO GDA-QT-PCL-TIT
                 COMPUTE GDA-VL-PCL-TIT = 140-VL-PCL-TIT *
                                          GDA-PERC-ANUD
                 MOVE GDA-VL-PCL-TIT   TO GDA-VL-ANUD
              ELSE
                 MOVE 140-QT-PCL-ADC   TO GDA-QT-PCL-ADC
                 COMPUTE GDA-VL-PCL-ADC = 140-VL-PCL-ADC *
                                          GDA-PERC-ANUD
                 MOVE GDA-VL-PCL-ADC   TO GDA-VL-ANUD
              END-IF
           ELSE
              IF CONTAS-CD-TITD-PORT EQUAL 1
                 MOVE 140-QT-PCL-TIT   TO GDA-QT-PCL-TIT
                 MOVE 140-VL-PCL-TIT   TO GDA-VL-PCL-TIT
                                          GDA-VL-ANUD
              ELSE
                 MOVE 140-QT-PCL-ADC   TO GDA-QT-PCL-ADC
                 MOVE 140-VL-PCL-ADC   TO GDA-VL-PCL-ADC
                                          GDA-VL-ANUD
              END-IF
           END-IF.
      *                                                                   VRS115
      * Tratamento diferenciado para contas de cartão empresarial         VRS115
      * em processo de cobrança de anuidade.                              VRS115
      *                                                                   VRS115
           IF (CONTAS-CD-MDLD-CRT EQUAL 03 OR 07 OR 31 OR 32
              OR 33 OR 34 OR 41 OR 42 OR 43 OR 56 OR 57 OR 58
              OR 71 OR 82 OR 95 OR 96 OR 114 OR 185 OR 186
              OR 97 OR 191 OR 197)
              IF CONTAS-NR-PCL-PND-ANUD GREATER ZEROS
                 IF GDA-IDENT-DSC EQUAL 'S'
                    COMPUTE GDA-VL-PCL-ADC = CONTAS-VL-PCL-ANUD *
                                             GDA-PERC-ANUD
                    MOVE GDA-VL-PCL-ADC      TO GDA-VL-ANUD
                 ELSE
                    MOVE CONTAS-VL-PCL-ANUD  TO GDA-VL-ANUD
                                             GDA-VL-PCL-ADC
                 END-IF
              END-IF
           END-IF.

       15000-99-EXIT.
           EXIT.

      *----------------------------------------------------------------*  VRS115
       15000-00-CALC-PRIM-SUB          SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'CALC. PRIM-SUB'       TO GDA-CURSOR.

           PERFORM 18500-00-VERIFICA-DSC-SUB.
           IF GDA-IDENT-DSC EQUAL 'S'
              PERFORM 19000-00-CALC-DSC-SUB
              IF CONTAS-CD-TITD-PORT EQUAL 1
                 MOVE 140-QT-PCL-TIT   TO GDA-QT-PCL-TIT
                 COMPUTE GDA-VL-PCL-TIT = 140-VL-PCL-TIT *
                                          GDA-PERC-ANUD
                 MOVE GDA-VL-PCL-TIT   TO GDA-VL-ANUD
              ELSE
                 MOVE 140-QT-PCL-ADC   TO GDA-QT-PCL-ADC
                 COMPUTE GDA-VL-PCL-ADC = 140-VL-PCL-ADC *
                                          GDA-PERC-ANUD
                 MOVE GDA-VL-PCL-ADC   TO GDA-VL-ANUD
              END-IF
           ELSE
              IF CONTAS-CD-TITD-PORT EQUAL 1
                 MOVE 140-QT-PCL-TIT   TO GDA-QT-PCL-TIT
                 MOVE 140-VL-PCL-TIT   TO GDA-VL-PCL-TIT
                                          GDA-VL-ANUD
              ELSE
                 MOVE 140-QT-PCL-ADC   TO GDA-QT-PCL-ADC
                 MOVE 140-VL-PCL-ADC   TO GDA-VL-PCL-ADC
                                          GDA-VL-ANUD
              END-IF
           END-IF.
      *                                                                   VRS115
      * Tratamento diferenciado para contas de cartão empresarial         VRS115
      * em processo de cobrança de anuidade.                              VRS115
      *                                                                   VRS115
           IF (CONTAS-CD-MDLD-CRT EQUAL 03 OR 07 OR 31 OR 32
              OR 33 OR 34 OR 41 OR 42 OR 43 OR 56 OR 57 OR 58
              OR 71 OR 82 OR 95 OR 96 OR 114 OR 185 OR 186
              OR 97 OR 191 OR 197)
      *                                                                   VRS115
              IF CONTAS-NR-PCL-PND-ANUD GREATER ZEROS
                 IF GDA-IDENT-DSC EQUAL 'S'
                    COMPUTE GDA-VL-PCL-ADC = CONTAS-VL-PCL-ANUD *
                                             GDA-PERC-ANUD
                    MOVE GDA-VL-PCL-ADC      TO GDA-VL-ANUD
                 ELSE
                    MOVE CONTAS-VL-PCL-ANUD  TO GDA-VL-ANUD
                                             GDA-VL-PCL-ADC
                 END-IF
              END-IF
           END-IF.

       15000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       16000-00-CALCULA-PRO-RATA       SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'CALC.PRO-RATA'        TO GDA-CURSOR.

           MOVE SPACES                 TO WS-PRORATA.
           MOVE 140-QT-PCL-ADC         TO WPRORAT-QT-ADC.
           MOVE 140-VL-PCL-ADC         TO WPRORAT-VL-ADC.

      *** ********************************************************* ***   VRS115
      *** Calcula a quantidade de parcelas Pro-rata para a cobranca ***   VRS115
      *** proporcional ao prazo restante.                           ***   VRS115
      *** ********************************************************* ***   VRS115
           COMPUTE GDA-QTPA    ROUNDED = ((WPRORAT-DIF-DATAS - 1) *
                                           WPRORAT-QT-ADC)    / 12.

           IF GDA-QTPA  EQUAL  ZEROS
              MOVE  1                  TO GDA-QTPA
           END-IF.

      *** ********************************************************* ***   VRS115
      *** Calcula o valor da parcela Pro-rata pelo total devido     ***   VRS115
      *** dividido pela quantidade de parcelas obtida (GDA-QTPA).   ***   VRS115
      *** ********************************************************* ***   VRS115
           COMPUTE GDA-VL-PRAT ROUNDED = ((WPRORAT-VL-ADC *
                                           WPRORAT-DIF-DATAS  / 12) *
                                           WPRORAT-QT-ADC) /
                                           GDA-QTPA.

           PERFORM 18500-00-VERIFICA-DESCONTO.

           IF GDA-IDENT-DSC EQUAL 'S'
              PERFORM 19000-00-CALC-DESCONTOS
              COMPUTE GDA-VL-PRAT ROUNDED = GDA-VL-PRAT * GDA-PERC-ANUD
           END-IF.

           IF (GDA-VL-PRAT  NOT EQUAL  140-VL-PCL-ADC) OR
              (GDA-QTPA     NOT EQUAL  140-QT-PCL-ADC)
              MOVE 'S'                 TO WS-PRORATA
           END-IF.

           MOVE GDA-VL-PRAT            TO GDA-VL-PCL-ADC
                                          GDA-VL-ANUD.
           MOVE GDA-QTPA               TO GDA-QT-PCL-ADC.
           MOVE GDA-DTA-ANI-TIT        TO CONTAS-DT-PRX-ANIV-ANUD.

       16000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       16000-00-CALC-PRORATA-SUB       SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'PRORATA SUB  '        TO GDA-CURSOR.

           MOVE SPACES                 TO WS-PRORATA.
           MOVE 140-QT-PCL-ADC         TO WPRORAT-QT-ADC.
           MOVE 140-VL-PCL-ADC         TO WPRORAT-VL-ADC.

      *** ********************************************************* ***   VRS115
      *** Calcula a quantidade de parcelas Pro-rata para a cobranca ***   VRS115
      *** proporcional ao prazo restante.                           ***   VRS115
      *** ********************************************************* ***   VRS115
           COMPUTE GDA-QTPA    ROUNDED = ((WPRORAT-DIF-DATAS - 1) *
                                           WPRORAT-QT-ADC)    / 12.

           IF GDA-QTPA  EQUAL  ZEROS
              MOVE  1                  TO GDA-QTPA
           END-IF.

      *** ********************************************************* ***   VRS115
      *** Calcula o valor da parcela Pro-rata pelo total devido     ***   VRS115
      *** dividido pela quantidade de parcelas obtida (GDA-QTPA).   ***   VRS115
      *** ********************************************************* ***   VRS115
           COMPUTE GDA-VL-PRAT ROUNDED = ((WPRORAT-VL-ADC *
                                           WPRORAT-DIF-DATAS  / 12) *
                                           WPRORAT-QT-ADC) /
                                           GDA-QTPA.

           PERFORM 18500-00-VERIFICA-DSC-SUB.

           IF GDA-IDENT-DSC EQUAL 'S'
              PERFORM 19000-00-CALC-DSC-SUB
              COMPUTE GDA-VL-PRAT ROUNDED = GDA-VL-PRAT * GDA-PERC-ANUD
           END-IF.

           IF (GDA-VL-PRAT  NOT EQUAL  140-VL-PCL-ADC) OR
              (GDA-QTPA     NOT EQUAL  140-QT-PCL-ADC)
              MOVE 'S'                 TO WS-PRORATA
           END-IF.

           MOVE GDA-VL-PRAT            TO GDA-VL-PCL-ADC
                                          GDA-VL-ANUD.
           MOVE GDA-QTPA               TO GDA-QT-PCL-ADC.
           MOVE GDA-DTA-ANI-TIT        TO CONTAS-DT-PRX-ANIV-ANUD.

       16000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       17000-00-ATUALIZA-ANO           SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'ATUALIZA ANO'         TO GDA-CURSOR.

           MOVE GDA-DB2-DIA            TO GDA-SBD-DIA.
           MOVE GDA-DB2-MES            TO GDA-SBD-MES.
           MOVE GDA-DB2-ANO            TO GDA-SBD-ANO.
           MOVE GDA-SBD-DATA           TO ARG01.

           IF GDA-AMD-MES = 2
              IF GDA-AMD-DIA GREATER 28
                 MOVE 28            TO GDA-AMD-DIA
              END-IF
           END-IF

           MOVE GDA-AMD-DIA            TO GDA-SBD-DIA.
           MOVE GDA-AMD-MES            TO GDA-SBD-MES.
           MOVE GDA-AMD-ANO            TO GDA-SBD-ANO.
           MOVE GDA-SBD-DATA           TO ARG02.

           MOVE ZEROS                  TO ARG03.

           CALL SBDATA USING FUNCAO ARG01 ARG02 ARG03.

           IF ARG01 EQUAL 99999999 OR
              ARG02 EQUAL 88888888
              PERFORM 90030-00-MENSAGEM-ERRO-003
           END-IF.

           IF ARG03  GREATER  60
      *** ********************************************************* ***   VRS115
      ***     Altera-se o dia de aniversario para evitar-se         ***   VRS115
      ***     distorcoes de calculos de anuidade inferiores a 1 ano ***   VRS115
      *** ********************************************************* ***   VRS115
              MOVE GDA-DATA-ATUAL      TO GDA-DATA-DB2
           END-IF.

       17000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       18000-00-CALCULA-DIF-DATAS      SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'CALC.DIF.DATAS'       TO GDA-CURSOR.

           IF (GDA-INDICADOR-CBR NOT EQUAL 2) OR
              (GDA-IN-CBR = 'N')
              MOVE 12                  TO WPRORAT-DIF-DATAS
              GO TO 18000-99-EXIT
           END-IF.

           MOVE GDA-ANI-DIA            TO GDA-SBD-DIA.
           MOVE GDA-ANI-MES            TO GDA-SBD-MES.
           MOVE GDA-ANI-ANO            TO GDA-SBD-ANO.
           MOVE GDA-SBD-DATA           TO ARG01.

           IF CONTAS-DT-PRX-ANIV-ANUD NOT EQUAL '01.01.0001'
              MOVE CONTAS-DT-PRX-ANIV-ANUD TO GDA-DATA-DB2
           ELSE
              MOVE GDA-DATA-ATUAL          TO GDA-DATA-DB2
           END-IF.

           MOVE GDA-DB2-DIA            TO GDA-SBD-DIA.
           MOVE GDA-DB2-MES            TO GDA-SBD-MES.
           MOVE GDA-DB2-ANO            TO GDA-SBD-ANO.
           MOVE GDA-SBD-DATA           TO ARG02.
           MOVE ZEROS                  TO ARG03.

           CALL SBDATA USING FUNCAO ARG01 ARG02 ARG03.

           IF ARG01 EQUAL 99999999 OR
              ARG02 EQUAL 88888888
              PERFORM 90030-00-MENSAGEM-ERRO-003
           END-IF.

           COMPUTE WPRORAT-DIF-DATAS ROUNDED = ARG03 / 30.

       18000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       18500-00-VERIFICA-DESCONTO      SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'VERIFICA DESC.'       TO GDA-CURSOR.

           EXEC SQL
                SELECT COUNT(*)
                  INTO :WCOUNT
                  FROM DB2VIP.DSC_ANUD
                 WHERE CD_ANUD = :CONTAS-CD-MDLD-CRT
           END-EXEC.

           MOVE SPACES                 TO GDA-IDENT-DSC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

           IF WCOUNT EQUAL ZEROS
              MOVE 'N'                 TO GDA-IDENT-DSC
           ELSE
              MOVE 'S'                 TO GDA-IDENT-DSC
           END-IF.

       18500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       18500-01-VERIFICA-DAA          SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           MOVE 'VERIFICA DAA.'       TO GDA-CURSOR.
           INITIALIZE PARM-VIPP4848
                      WCOUNT2.
      *                                                                   VRS115
           IF CONTAS-NR-SEQL-TITD-PORT = 1
              MOVE CONTAS-CD-SUB-MDLD-CRT TO GDA-SUB-MDLD
           ELSE
              PERFORM 18500-02-BUSCA-SUB-TIT
           END-IF.
      *                                                                   VRS115
           EXEC SQL
                SELECT COUNT(*)
                  INTO :WCOUNT2
                  FROM DB2VIP.SUB_MDLD_GR
                 WHERE CD_MDLD_CRT_CRD    = :CONTAS-CD-MDLD-CRT
                   AND CD_SUB_MDLD_CRT    = :GDA-SUB-MDLD
                   AND CD_GR_SUB_MDLD     = 114
                 FETCH FIRST 1 ROWS ONLY
           END-EXEC.
      *                                                                   VRS115
           IF SQLCODE NOT EQUAL ZEROS AND 100
              PERFORM 999018-ERRO-18
           END-IF.
      *                                                                   VRS115
           IF WCOUNT2 NOT EQUAL ZEROS
              PERFORM 14000-02-CALCULA-DAA
           END-IF.
      *                                                                   VRS115
       18500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       18500-02-BUSCA-SUB-TIT          SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           MOVE 'BUSCA-SUB-TIT.'       TO GDA-CURSOR.
      *                                                                   VRS115
           EXEC SQL
                SELECT CD_SUB_MDLD_CRT
                  INTO :GDA-SUB-MDLD
                  FROM DB2VIP.PORT_CRT
                 WHERE NR_CT_CRT = :CONTAS-NR-CT-CRT
                   AND NR_SEQL_TITD_PORT = 1
           END-EXEC.
      *                                                                   VRS115
           IF SQLCODE NOT EQUAL ZEROS AND 100
              PERFORM 999018-ERRO-19
           END-IF.
      *                                                                   VRS115
       18500-99-EXIT.
           EXIT.
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
       19000-00-CALC-DESCONTOS         SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'OPEN DESCONTO'        TO GDA-CURSOR.

           EXEC SQL
                OPEN DESCONTO
           END-EXEC.

           MOVE ZEROS                  TO WIND-DESC.
           MOVE SPACES                 TO GDA-CONTROL.

           PERFORM 19500-00-MONTA-TAB-DESC
                   UNTIL SQLCODE EQUAL +100 OR
                   WIND-DESC > 12.

           MOVE 'CLOSE DESCONTO'       TO GDA-CURSOR.

           EXEC SQL
                CLOSE DESCONTO
           END-EXEC.

           IF GDA-CONTROL NOT EQUAL '*'
              PERFORM 20000-00-PROCESSA-DESCONTO
              IF GDA-PERC-DESC GREATER ZEROS AND
                 GDA-PERC-DESC LESS    100
                 COMPUTE GDA-PERC-ANUD ROUNDED = (100 - GDA-PERC-DESC) /
                                                           100
              ELSE
                 IF GDA-PERC-DESC  EQUAL  100
                    MOVE ZEROS         TO GDA-PERC-ANUD
                 ELSE
                    MOVE 1             TO GDA-PERC-ANUD
                 END-IF
              END-IF
           END-IF.

       19000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       18500-00-VERIFICA-DSC-SUB       SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'VERIF DSC-SUB.'       TO GDA-CURSOR.

           EXEC SQL
                SELECT COUNT(*)
                  INTO :WCOUNT
                  FROM DB2VIP.DSC_ANUD_SUB_MDLD
                 WHERE CD_MDLD_CRT_CRD = :GDA-CD-MDLD-CRT-CRD
                   AND CD_SUB_MDLD_CRT = :GDA-CD-SUB-MDLD-CRT
           END-EXEC.

           MOVE SPACES                 TO GDA-IDENT-DSC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

           IF WCOUNT EQUAL ZEROS
              MOVE 'N'                 TO GDA-IDENT-DSC
           ELSE
              MOVE 'S'                 TO GDA-IDENT-DSC
           END-IF.


       18500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       19000-00-CALC-DSC-SUB           SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'OPEN DSC-SUB '        TO GDA-CURSOR.

           EXEC SQL
                OPEN DSC-SUB
           END-EXEC.

           MOVE ZEROS                  TO WIND-DESC.
           MOVE SPACES                 TO GDA-CONTROL.

           PERFORM 19500-00-MONTA-TAB-DSC-SUB
                   UNTIL SQLCODE EQUAL +100 OR
                   WIND-DESC > 12.

           MOVE 'CLOSE DSC-SUB '       TO GDA-CURSOR.

           EXEC SQL
                CLOSE DSC-SUB
           END-EXEC.

           IF GDA-CONTROL NOT EQUAL '*'
              PERFORM 20000-00-PROCESSA-DESCONTO

              IF GDA-PERC-DESC GREATER ZEROS AND
                 GDA-PERC-DESC LESS    100
                 COMPUTE GDA-PERC-ANUD ROUNDED = (100 - GDA-PERC-DESC) /
                                                           100
              ELSE
                 IF GDA-PERC-DESC  EQUAL  100
                    MOVE ZEROS         TO GDA-PERC-ANUD
                 ELSE
                    MOVE 1             TO GDA-PERC-ANUD
                 END-IF
              END-IF
           END-IF.

       19000-99-EXIT.
           EXIT.
      *---------------------------------------*                           VRS115
       19200-00-MONTA-TAB-GRMDLD       SECTION.
      *---------------------------------------*                           VRS115
           MOVE 'FETCH GRMDLD  '       TO GDA-CURSOR.

           EXEC SQL
                FETCH GRMDLD
                 INTO :GRMDLD-CD-MDLD-CRT
           END-EXEC.

           IF WIND-GRMDLD EQUAL 1
              IF SQLCODE NOT EQUAL 0
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    MOVE '*'           TO GDA-CONTROL
                    GO TO 19200-99-EXIT
                 END-IF
              END-IF
           ELSE
              IF SQLCODE NOT EQUAL ZEROS
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    COMPUTE WIND-FIM-GRMDLD = WIND-GRMDLD - 1
                    GO TO 19200-99-EXIT
                 END-IF
              END-IF
           END-IF.

           IF GRMDLD-CD-MDLD-CRT        GREATER  ZEROS
              MOVE GRMDLD-CD-MDLD-CRT   TO  TAB-CD-MDLD-CRT(WIND-GRMDLD)
           ELSE
              MOVE 21                   TO  WIND-GRMDLD
           END-IF.

       19200-99-EXIT.
           EXIT.
      *---------------------------------------*                           VRS115
       19400-00-MONTA-TAB-GRMDNAC      SECTION.
      *---------------------------------------*                           VRS115
           MOVE 'FETCH GRMDNAC '       TO GDA-CURSOR.

           EXEC SQL
                FETCH GRMDNAC
                 INTO :GRMDLD-CD-MDLD-CRT
           END-EXEC.

           IF WIND-GRMDLD EQUAL 1
              IF SQLCODE NOT EQUAL 0
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    MOVE '*'           TO GDA-CONTROL
                    GO TO 19400-99-EXIT
                 END-IF
              END-IF
           ELSE
              IF SQLCODE NOT EQUAL ZEROS
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    COMPUTE WIND-FIM-GRMDLD = WIND-GRMDLD - 1
                    GO TO 19400-99-EXIT
                 END-IF
              END-IF
           END-IF.

           IF GRMDLD-CD-MDLD-CRT        GREATER  ZEROS
              MOVE GRMDLD-CD-MDLD-CRT   TO  TAB-CD-MDLD-NAC(WIND-GRMDLD)
           ELSE
              MOVE 21                   TO  WIND-GRMDLD
           END-IF.

       19400-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       19500-00-MONTA-TAB-DESC         SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'FETCH DESCONTO'       TO GDA-CURSOR.

           ADD 1                       TO WIND-DESC

           EXEC SQL
                FETCH DESCONTO
                 INTO :DESCONTO-DT-VIGENCIA,
                      :DESCONTO-FAIXA,
                      :DESCONTO-PERCENTUAL,
                      :DESCONTO-VALOR
           END-EXEC.

           IF WIND-DESC EQUAL 1
              IF SQLCODE NOT EQUAL 0
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    MOVE '*'           TO GDA-CONTROL
                    GO TO 19500-99-EXIT
                 END-IF
              END-IF
           ELSE
              IF SQLCODE NOT EQUAL ZEROS
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    COMPUTE WIND-FIM = WIND-DESC - 1
                    GO TO 19500-99-EXIT
                 END-IF
              END-IF
           END-IF.

           IF DESCONTO-FAIXA GREATER ZEROS
              MOVE DESCONTO-FAIXA          TO FAIXA-DESCONTO(WIND-DESC)
              IF DESCONTO-PERCENTUAL GREATER ZEROS
                 MOVE DESCONTO-PERCENTUAL  TO VALOR-DESCONTO(WIND-DESC)
              ELSE
                 MOVE DESCONTO-VALOR       TO VALOR-DESCONTO(WIND-DESC)
              END-IF
           ELSE
              MOVE 13                      TO WIND-DESC
           END-IF.

       19500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       19500-00-MONTA-TAB-DSC-SUB      SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'FETCH DSC-SUB'        TO GDA-CURSOR.

           ADD 1                       TO WIND-DESC

           EXEC SQL
                FETCH DSC-SUB
                 INTO :DESCONTO-DT-VIGENCIA
                    , :DESCONTO-FAIXA
                    , :DESCONTO-PERCENTUAL
                    , :DESCONTO-VALOR
           END-EXEC.

           IF WIND-DESC EQUAL 1
              IF SQLCODE NOT EQUAL 0
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    MOVE '*'           TO GDA-CONTROL
                    GO TO 19500-99-EXIT
                 END-IF
              END-IF
           ELSE
              IF SQLCODE NOT EQUAL ZEROS
                 IF SQLCODE NOT EQUAL +100
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 ELSE
                    COMPUTE WIND-FIM = WIND-DESC - 1
                    GO TO 19500-99-EXIT
                 END-IF
              END-IF
           END-IF.

           IF DESCONTO-FAIXA GREATER ZEROS
              MOVE DESCONTO-FAIXA          TO FAIXA-DESCONTO(WIND-DESC)
              IF DESCONTO-PERCENTUAL GREATER ZEROS
                 MOVE DESCONTO-PERCENTUAL  TO VALOR-DESCONTO(WIND-DESC)
              ELSE
                 MOVE DESCONTO-VALOR       TO VALOR-DESCONTO(WIND-DESC)
              END-IF
           ELSE
              MOVE 13                      TO WIND-DESC
           END-IF.

       19500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       20000-00-PROCESSA-DESCONTO      SECTION.
      *----------------------------------------------------------------*  VRS115
           MOVE 'PROC. DESCONTOS'      TO GDA-CURSOR.

           MOVE ZEROS                  TO GDA-COUNT-CRT
                                          GDA-NR-SEQL-FAT-CT-CRT
                                          GDA-VL-SDO-FAT-CT-CRT
                                          WIND-DESC
                                          GDA-PERC-DESC.

           IF CONTAS-CD-MDLD-CRT  EQUAL  03 OR 07
              EXEC SQL
                   SELECT COUNT(*)
                     INTO :GDA-COUNT-CRT
                     FROM DB2VIP.CT_CRT
                    WHERE CD_CLI      = :CONTAS-CD-CLI
                      AND CD_MDLD_CRT = :CONTAS-CD-MDLD-CRT
                      AND DT_FIM_CT   = '01.01.0001'
              END-EXEC

              IF SQLCODE NOT EQUAL ZEROS
                 MOVE 'SELECT COUNT'   TO GDA-CURSOR
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF

           END-IF.

           IF CONTAS-CD-MDLD-CRT EQUAL 31 OR 32 OR 33
                                 OR 56 OR 57 OR 58 OR 185 OR 186 OR 197

              MOVE  0  TO  GDA-NR-SEQL-FAT-CT-CRT

      *       Alteracao na busca da ultima fatura fechada, em funcao      VRS115
      *       da reinicializacao do parametro NR_SEQL_FAT_CT_CRT.         VRS115
      *       A ultima fatura deve ter o maior Código de Calendario.      VRS115
      *       --------------------------------------------------------    VRS115

              EXEC SQL
                   SELECT MAX(NR_SEQL_FAT_CT_CRT)
                     INTO :GDA-NR-SEQL-FAT-CT-CRT:INULL-DESC-MAX
                     FROM DB2VIP.FAT_CT_CRT
                    WHERE NR_CTR_OPR_CT_CRT = :CONTAS-NR-CT-CRT
                      AND CD_CLDR_FATM = ( SELECT MAX(A.CD_CLDR_FATM)
                                             FROM DB2VIP.FAT_CT_CRT A
                                            WHERE A.NR_CTR_OPR_CT_CRT
                                                = :CONTAS-NR-CT-CRT
                                              AND A.CD_CLDR_FATM > 0 )
              END-EXEC

              IF SQLCODE NOT EQUAL ZEROS
                 MOVE 'SELECT MAX'     TO GDA-CURSOR
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF

              IF INULL-DESC-MAX  LESS  ZEROS
                 MOVE ZEROS            TO GDA-COUNT-CRT
              END-IF

              IF GDA-NR-SEQL-FAT-CT-CRT  GREATER  ZEROS
                 EXEC SQL
                   SELECT SUM(VL_SDO_FAT_CT_CRT)
                     INTO :GDA-VL-SDO-FAT-CT-CRT:INULL-DESC-SUM
                     FROM DB2VIP.SDO_FAT_CT_CRT
                    WHERE NR_SEQL_FAT_CT_CRT = :GDA-NR-SEQL-FAT-CT-CRT
                      AND CD_TIP_SDO        IN (2, 4, 5, 109)
                 END-EXEC

                 IF SQLCODE NOT EQUAL ZEROS
                    MOVE 'SELECT SUM'  TO GDA-CURSOR
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 END-IF

                 IF INULL-DESC-SUM  LESS  ZEROS
                    MOVE ZEROS         TO GDA-COUNT-CRT
                 ELSE
                    MOVE GDA-VL-SDO-FAT-CT-CRT  TO GDA-COUNT-CRT
                 END-IF

              ELSE
                 MOVE ZEROS            TO GDA-COUNT-CRT
              END-IF

           END-IF.

           IF FAIXA-DESCONTO(WIND-FIM)  NOT GREATER  GDA-COUNT-CRT
              MOVE VALOR-DESCONTO(WIND-FIM)   TO GDA-PERC-DESC
           ELSE
              PERFORM 20500-00-OBTEM-FAIXA-DESC
                      UNTIL WIND-DESC > 12
           END-IF.

       20000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       20500-00-OBTEM-FAIXA-DESC       SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'OBTEM FAIXA DSC'      TO GDA-CURSOR.

           ADD 1                       TO WIND-DESC.

           IF FAIXA-DESCONTO(WIND-DESC) NOT GREATER GDA-COUNT-CRT  AND
              FAIXA-DESCONTO(WIND-DESC + 1) GREATER GDA-COUNT-CRT
              MOVE VALOR-DESCONTO(WIND-DESC)  TO GDA-PERC-DESC
              MOVE 13                         TO WIND-DESC
           END-IF.

       20500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       21000-00-ATUALIZA-PROMOCAO      SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'OPEN PROMOCAO'        TO GDA-CURSOR.

           EXEC SQL
                OPEN PROMOCAO
           END-EXEC.

           PERFORM 22000-00-GRAVA-PROMOCAO
                   UNTIL SQLCODE EQUAL +100.

           MOVE 'CLOSE PROMOCAO'       TO GDA-CURSOR.

           EXEC SQL
                CLOSE PROMOCAO
           END-EXEC.

       21000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       22000-00-GRAVA-PROMOCAO         SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'GRAVA PROMOCAO'       TO GDA-CURSOR.

           EXEC SQL
                FETCH PROMOCAO
                 INTO :GDA-QT-AA-VLD,
101219                :GDA-CD-ANUD
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              IF SQLCODE NOT EQUAL +100
                 PERFORM 90010-00-MENSAGEM-ERRO-001
              END-IF
           ELSE
              COMPUTE GDA-QT-AA-VLD = GDA-QT-AA-VLD - 1
              IF GDA-QT-AA-VLD NOT GREATER ZEROS
                 EXEC SQL
                   DELETE FROM DB2VIP.ANUD_PORT
                    WHERE CD_ANUD           = :GDA-CD-ANUD
                      AND NR_CT_CRT         = :CONTAS-NR-CT-CRT
                      AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
                 END-EXEC
                 IF SQLCODE NOT EQUAL ZEROS
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 END-IF
              ELSE
                 EXEC SQL
                   UPDATE DB2VIP.ANUD_PORT
                      SET QT_AA_VLD_ANUD    = :GDA-QT-AA-VLD
                    WHERE CD_ANUD           = :GDA-CD-ANUD
                      AND NR_CT_CRT         = :CONTAS-NR-CT-CRT
                      AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
                 END-EXEC
                 IF SQLCODE NOT EQUAL ZEROS
                    PERFORM 90010-00-MENSAGEM-ERRO-001
                 END-IF
              END-IF
           END-IF.

       22000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       24000-00-DESCONTO-OCI           SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE 'DESCONTO OCI'         TO GDA-CURSOR.

           IF WK-BB-CODIGO-OCI EQUAL 100
              MOVE 1                   TO WDESCONTO-OCI
           ELSE
              COMPUTE WDESCONTO-OCI = (WK-BB-CODIGO-OCI - 100) / 100
           END-IF.

           MOVE SPACES                 TO WDESCRICAO
           MOVE GDA-PARCELA            TO WPARC-PEND
           MOVE CONTAS-QT-TTL-PCL-ANUD TO WPARC-TOTAL.

           IF CONTAS-CD-TITD-PORT = 1
              STRING 'DESCONTO TIT - PARC ' WPARC-PEND
                      DELIMITED BY SIZE
                      '/' WPARC-TOTAL
                      DELIMITED BY SIZE     INTO WDESCRICAO
           ELSE
              STRING 'DESCONTO ADC - PARC ' WPARC-PEND
                      DELIMITED BY SIZE
                      '/' WPARC-TOTAL
                      DELIMITED BY SIZE     INTO WDESCRICAO
           END-IF.

           MOVE  SPACES                TO LK82-PARAMETROS
                                           LK82-RETORNO.
           MOVE  CONTAS-NR-CT-CRT      TO LK82-NR-CT-CRT.
           MOVE  CONTAS-NR-PLST        TO LK82-NR-PLST.
           MOVE  GDA-DATA-ATUAL        TO LK82-DT-EFT-TRAN
                                          LK82-DT-MVT-CT-CRT.
           MOVE  WDESCRICAO            TO LK82-TX-MVT-CT-CRT.

           COMPUTE LK82-VL-MOE-OGNL-MVT = CONTAS-VL-PCL-ANUD *
                                          WDESCONTO-OCI.


           MOVE LK82-VL-MOE-OGNL-MVT   TO LK82-VL-MVT-CT-CRT
                                          GDA-VL-DSC-PORT
                                          CONTAS-VL-PCL-ANUD.

           MOVE 'ANU'                  TO LK82-SG-SSIS-OGM.
           MOVE 613000                 TO LK82-CD-TRAN.
           MOVE 1001                   TO LK82-CD-DET-TRAN.
           MOVE '2'                    TO LK82-IN-PSTG.
           MOVE CONTAS-NR-CT-CRT       TO LK82-NR-CTL-SSIS-OGM.
           MOVE '986'                  TO LK82-CD-MOE-OGNL.
           MOVE 21                     TO LK82-CD-PLN-VIP.
           MOVE 100                    TO LK82-CD-ORG.
           MOVE 'VIPP0007'             TO LK82-CD-USU-RSP-LCTO.
           MOVE SPACES                 TO LK82-CD-AUTZ-TRAN
                                          LK82-CD-MDU-PRCR
                                          LK82-CD-ITCB-CRT.
           MOVE CONTAS-CD-MDLD-CRT     TO LK82-NR-TIP-MDLD.
           MOVE ZEROS                  TO LK82-NR-CMPT-PLST
                                          LK82-VL-US-MVT-CT-CRT
                                          LK82-NR-CTR-NEGO
                                          LK82-IND-ERRO
                                          LK82-EIBRESP
                                          LK82-NR-PCL-MVT-CPR
                                          LK82-QT-PCL-MVT-CPR
                                          LK82-VL-CNV-DT-CPR
                                          LK82-NR-IDFR-TRAN-C.
           MOVE 'S'                    TO LK82-IND-TIPO-COMP.

           PERFORM 14600-00-BUSCA-REFNUMBER.
           CALL VIPP0082 USING LK82-MVT-PARAM

      *
      * MOCK-POINT FORCA-ERRO-003
      *

           IF LK82-IND-ERRO NOT EQUAL ZEROS
              PERFORM  999017-ERRO-17
           END-IF

           ADD 1                       TO WCOMMIT
                                             WGRAVADOS

           EXEC SQL
                UPDATE DB2VIP.PORT_CRT
                   SET VL_ANUD_FATD      = VL_ANUD_FATD
                                         - :CONTAS-VL-PCL-ANUD
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT
                   AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              PERFORM 90010-00-MENSAGEM-ERRO-001
           END-IF.

           IF  WCOMMIT GREATER  10
               MOVE 'COMMIT PARCIAL'   TO GDA-CURSOR
               MOVE GDA-DATA-VIP7      TO 207-VL-TIP-DT
               MOVE GDA-CTRL-CICLO     TO 207-QT-DCML
               PERFORM 14500-00-ATUALIZA-LIDER
               EXEC   SQL  COMMIT   END-EXEC
               IF SQLCODE NOT EQUAL ZEROS
                  PERFORM 90010-00-MENSAGEM-ERRO-001
               END-IF
               MOVE 0                  TO WCOMMIT
           END-IF.
           PERFORM 290000-00-GRAVA-MVT-ANUD.

       24000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       250000-00-LER-ARQ-VIPF904E          SECTION.
      *----------------------------------------------------------------*
      *                                                                   VRS115
           MOVE ZEROS TO 904-DETALHE
      *                                                                   VRS115
           READ VIPF904E INTO 904-DETALHE
             AT END
                MOVE 1               TO FIM-VIPF904
                MOVE 999999999999999 TO 904-NR-CT-CRT
           END-READ.

           IF 904-NR-CT-CRT          EQUAL 4454933 OR 4469338
                DISPLAY '904-PC-DSC-ANUD-CTRA' 904-PC-DSC-ANUD-CTRA
           END-IF.

       25000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       260000-00-GRAVA-VIPFERRO            SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           INITIALIZE VIPKERRO
           MOVE CONTAS-NR-CT-CRT            TO VIPKERRO-NR-CRT
           MOVE CONTAS-NR-SEQL-TITD-PORT    TO VIPKERRO-SEQ-TIT
           STRING
              'Conta cartao nao encontrada no VIPF904E, '
              'espelho do AMBS'
              DELIMITED BY SIZE
              INTO VIPKERRO-MSG-ERRO
           END-STRING
      *                                                                   VRS115
           WRITE FD-REG-VIPFERRO          FROM  VIPKERRO.
       26000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       270000-00-GRAVA-VIPFCANU            SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           INITIALIZE VIPKCONF
      *                                                                   VRS115
           MOVE CONTAS-NR-CT-CRT            TO VIPKCONF-NR-CRT
           MOVE CONTAS-NR-SEQL-TITD-PORT    TO VIPKCONF-SEQ-TIT
           MOVE 904-DT-PRI-COMPRA           TO VIPKCONF-DT-PRI-COMPRA
           MOVE CONTAS-CD-CLI            TO VIPKCONF-CD-CLI               VRS128
           MOVE CONTAS-CD-MDLD-CRT       TO VIPKCONF-CD-MDLD-CRT          VRS128
           MOVE CONTAS-CD-TITD-PORT      TO VIPKCONF-CD-TITD-PORT         VRS128
           MOVE CONTAS-CD-TIP-CBR-ANUD   TO VIPKCONF-CD-TIP-CBR-ANUD      VRS128
           MOVE CONTAS-IN-CBR-ANUD       TO VIPKCONF-IN-CBR-ANUD          VRS128
           MOVE CONTAS-DT-PRX-ANIV-ANUD  TO VIPKCONF-DT-PRX-ANIV-ANUD     VRS128
           MOVE CONTAS-DT-PRMO-CBR-ANUD  TO VIPKCONF-DT-PRMO-CBR-ANUD     VRS128
           MOVE CONTAS-DT-INC-CBR-ANUD   TO VIPKCONF-DT-INC-CBR-ANUD      VRS128
           MOVE CONTAS-NR-PCL-PND-ANUD   TO VIPKCONF-NR-PCL-PND-ANUD      VRS128
           MOVE CONTAS-VL-PCL-ANUD       TO VIPKCONF-VL-PCL-ANUD          VRS128
           MOVE CONTAS-QT-TTL-PCL-ANUD   TO VIPKCONF-QT-TTL-PCL-ANUD      VRS128
           MOVE CONTAS-CD-SUB-MDLD-CRT   TO VIPKCONF-CD-SUB-MDLD-CRT      VRS128
           MOVE CONTAS-CD-ANUD-LIDO      TO VIPKCONF-CD-ANUD-LIDO         VRS128
           MOVE CONTAS-VL-ANUD-FATD      TO VIPKCONF-VL-ANUD-FATD         VRS128
      *                                                                   VRS115
           WRITE FD-REG-VIPFCANU          FROM  VIPKCONF.
       27000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*
       271000-00-CALCULA-DESCONTOS            SECTION.
      *----------------------------------------------------------------*
      *
           MOVE ZEROS                     TO GDA-VL-MCI
                                             GDA-VL-4865
                                             GDA-VL-4848
                                             GDA-VL-904
                                             GDA-VL-CTRA
                                             GDA-VL-INV
                                             GDA-MAIOR
           MOVE SPACES                    TO GDA-TIPO
      *
      * DAA por código de cliente
      *
           PERFORM 272000-00-RECUPERA-DESC-MCI
           IF VIPST05V-PC-DSC-MSLD-S NOT EQUAL ZEROS OR
              VIPST05V-VL-DSC-MSLD-S NOT EQUAL ZEROS
              IF VIPST05V-PC-DSC-MSLD-S NOT EQUAL ZEROS
                 COMPUTE GDA-VL-MCI = CONTAS-VL-PCL-ANUD
                                    * (VIPST05V-PC-DSC-MSLD-S / 100)
              ELSE
                 IF VIPST05V-VL-DSC-MSLD-S GREATER  CONTAS-VL-PCL-ANUD
                    MOVE CONTAS-VL-PCL-ANUD     TO  GDA-VL-MCI
                 ELSE
                    MOVE VIPST05V-VL-DSC-MSLD-S TO GDA-VL-MCI
                 END-IF
              END-IF
              MOVE 'MCI'                        TO GDA-TIPO
              MOVE GDA-VL-MCI                   TO GDA-MAIOR
             END-IF
      *
      * DAA por encarteiramento
      *
      *    IF 904-DSC-ENCT > 0
      *
      *       COMPUTE GDA-VL-ESTN-DAA =
      *            CONTAS-VL-PCL-ANUD * ( 904-DSC-ENCT / 100)
      *       IF GDA-VL-ESTN-DAA EQUAL ZEROS
      *          MOVE 0,01                    TO GDA-VL-ESTN-DAA
      *       END-IF
      *       MOVE GDA-VL-ESTN-DAA            TO GDA-VL-904
      *
      *       IF GDA-VL-ESTN-DAA GREATER GDA-MAIOR
      *          MOVE '904'                   TO GDA-TIPO
      *          MOVE GDA-VL-ESTN-DAA         TO GDA-MAIOR
      *       END-IF
      *    END-IF
      *
      * DAA por saldo de gasto do cartão
      *
           IF GDA-DT-ABTR-CT-INV NOT LESS GDA-DTABTDAA-INV
              PERFORM 14700-00-BUSCA-GSTO

              IF VIPK4865-VL-DSC GREATER GDA-MAIOR
                 MOVE 'DAA'                   TO GDA-TIPO
                 MOVE VIPK4865-VL-DSC         TO GDA-MAIOR
                                                 GDA-VL-4865
              END-IF
           ELSE
               PERFORM 18500-01-VERIFICA-DAA
               IF 048W-VL-DSC GREATER GDA-MAIOR
                  MOVE 'DAA'                   TO GDA-TIPO
                  MOVE 048W-VL-DSC             TO GDA-MAIOR
                                                  GDA-VL-4848
               END-IF
           END-IF

      *
      * DAA por investimento
      *
      *    MOVE ZEROS                      TO GDA-VL-INVS
      *
      *    IF 904-IN-DSC-INV EQUAL 'S'
      *     IF 904-VL-INVS-CLI NOT LESS 904-VL-INVS-MIN AND
      *        904-SDO-ATUA    NOT LESS 904-VL-GSTO-MIN
      *        IF 904-VL-DSC-ANUD-N NOT EQUAL '?'
      *           IF 904-VL-DSC-ANUD NOT LESS CONTAS-VL-PCL-ANUD
      *              MOVE CONTAS-VL-PCL-ANUD  TO GDA-VL-INVS
      *           ELSE
      *              MOVE 904-VL-DSC-ANUD     TO GDA-VL-INVS
      *           END-IF
      *        ELSE
      *         IF 904-PC-DSC-ANUD-N NOT EQUAL '?'
      *            COMPUTE GDA-PERC = 100 - 904-PC-DSC-ANUD
      *            COMPUTE GDA-VL-INVS = CONTAS-VL-PCL-ANUD
      *                                - ((CONTAS-VL-PCL-ANUD
      *                                *  GDA-PERC)
      *                                /   100)
      *         END-IF
      *        END-IF
      *     END-IF
      *    END-IF

      *
      * DAA por carteira
      *
           COMPUTE GDA-VL-CTRA =
                   CONTAS-VL-PCL-ANUD * ( 904-PC-DSC-ANUD-CTRA / 100)

           IF GDA-VL-CTRA GREATER GDA-MAIOR
              MOVE 'CTR'                      TO GDA-TIPO
              MOVE GDA-VL-CTRA                TO GDA-MAIOR
           END-IF

      *
      * DAA por investimento
      *
           COMPUTE GDA-VL-INV =
                   CONTAS-VL-PCL-ANUD * ( 904-PC-DSC-ANUD-INV / 100)

           IF GDA-VL-INV GREATER GDA-MAIOR
              MOVE 'INV'                     TO GDA-TIPO
              MOVE GDA-VL-INV                TO GDA-MAIOR
           END-IF

      *                                                                   VRS134
      * MOCK-POINT FORCA-ERRO-008
      *
           IF GDA-MAIOR GREATER ZEROS
                INITIALIZE DCLAPL-DSC-AUTC-ANUD
                COMPUTE 0A1-PC-DSC-ATBD =
                   (GDA-MAIOR / CONTAS-VL-PCL-ANUD) * 100
           ELSE
                MOVE ZEROS                     TO 0A1-PC-DSC-ATBD
           END-IF

           IF 904-VL-INV-CLI GREATER ZEROS
                PERFORM 32000-00-MONTA-TAB-S1VIP0A1
           END-IF
      *                                                                   VRS134

           IF GDA-MAIOR EQUAL ZEROS
              MOVE 0,01                        TO GDA-MAIOR
           END-IF
           MOVE GDA-MAIOR                      TO GDA-VL-ESTN-DAA
      *
      * MOCK-POINT FORCA-ERRO-006
      *
           EVALUATE GDA-TIPO
      *      WHEN '904'
      *           PERFORM 27500-00-ESTORNO-CARTEIRA
             WHEN 'DAA'
             WHEN 'MCI'
             WHEN 'CTR'
             WHEN 'INV'
                  MOVE  SPACES             TO VIPKANUD
                  MOVE  GDA-TIPO           TO VIPKANUD-DAA
                  MOVE  CONTAS-NR-CT-CRT   TO VIPKANUD-NR-CT-CRT-DAA
                  MOVE  CONTAS-CD-MDLD-CRT TO VIPKANUD-CD-MDLD-CRT-DAA
                  MOVE  GDA-SUB-MDLD       TO VIPKANUD-CD-SUBMDLD-DAA
                  MOVE  CONTAS-NR-PLST     TO VIPKANUD-NR-PLST-DAA
                  MOVE  GDA-DATA-ATUAL     TO VIPKANUD-DATA-ATUAL-DAA
                  MOVE  CONTAS-CD-CLI      TO VIPKANUD-CD-CLIENTE-DAA
                  MOVE  CONTAS-NR-SEQL-TITD-PORT
                                           TO VIPKANUD-NR-SEQL-TITD-DAA
                  MOVE  GDA-VL-ANUD        TO VIPKANUD-VL-PCL-ANUD-DAA
                  MOVE  GDA-MAIOR          TO VIPKANUD-VL-DSC-ANUD-DAA
                  MOVE  GDA-VL-904         TO VIPKANUD-VL-DSC-904
                  MOVE  GDA-VL-MCI         TO VIPKANUD-VL-DSC-MCI
                  MOVE  GDA-VL-CTRA        TO VIPKANUD-VL-DSC-CTRA
                  MOVE  GDA-VL-INV         TO VIPKANUD-VL-DSC-INV
                  MOVE  GDA-VL-4865        TO VIPKANUD-VL-DSC-4865
                  MOVE  GDA-VL-4848        TO VIPKANUD-VL-DSC-4848
                  ADD   1                  TO GDA-REG-GRAV-ANUD
                  WRITE FD-REG-VIPFANUD    FROM  VIPKANUD
                  PERFORM 14000-02-GRAVA-MOVTO-DAA
             END-EVALUATE
           .
       271000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*
       272000-00-RECUPERA-DESC-MCI                SECTION.
      *----------------------------------------------------------------*
      *
           MOVE 2                          TO VIPST05V-FUNCAO
      * MOCK-POINT MCKV01 MOCK DA VARIáVEL CONTAS-NR-CT-CRT
           MOVE CONTAS-NR-CT-CRT           TO VIPST05V-NR-CT-CRT
           MOVE ZEROS                      TO VIPST05V-PC-DSC-MSLD
                                              VIPST05V-VL-DSC-MSLD
           MOVE SPACES                     TO VIPST05V-DT-FIM-VGC-DSC

           MOVE LENGTH OF PARM-VIPST05V    TO EIBCALEN
           CALL VIPST05V USING DFHEIBLK PARM-VIPST05V
*
           EVALUATE VIPST05V-CD-ERRO
               WHEN 0
                    CONTINUE
               WHEN 11
                    MOVE ZEROS            TO VIPST05V-PC-DSC-MSLD-S
                                             VIPST05V-VL-DSC-MSLD-S
               WHEN OTHER
                   PERFORM  999020-ERRO-20
           END-EVALUATE
           .
       272000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS119
       27500-00-ESTORNO-CARTEIRA        SECTION.                          VRS119
      *----------------------------------------------------------------*  VRS119
           MOVE 'INSERT ENCARTEIRAMENTO'      TO GDA-CURSOR.              VRS119
      *                                                                   VRS119
      *    COMPUTE GDA-VL-ESTN-DAA =                                      VRS119
      *            CONTAS-VL-PCL-ANUD * ( 904-DSC-ENCT / 100).

           IF  GDA-VL-ESTN-DAA EQUAL ZEROS
               MOVE 0,01 TO GDA-VL-ESTN-DAA
           END-IF

           MOVE SPACES                 TO WDESCRICAO                      VRS119
      *     MOVE GDA-PARCELA            TO WPARC-PEND                     VRS119
      *     MOVE CONTAS-QT-TTL-PCL-ANUD TO WPARC-TOTAL.                   VRS119

           STRING 'Cliente ' 904-NM-TIP-CTRA DELIMITED BY SIZE            VRS120
                  '- estorno '               DELIMITED BY SIZE            VRS120
           INTO WDESCRICAO                                                VRS119
      *        WPARC-PEND DELIMITED BY SIZE                               VRS119
      *                '/' WPARC-TOTAL
           ADD  1                      TO GDA-REG-DSC-ENCT                VRS120

           MOVE SPACES                 TO LK82-PARAMETROS                 VRS119
                                          LK82-RETORNO.                   VRS119
           MOVE CONTAS-NR-CT-CRT       TO LK82-NR-CT-CRT                  VRS119
                                          LK82-NR-CTL-SSIS-OGM.           VRS119
           MOVE CONTAS-NR-PLST         TO LK82-NR-PLST.                   VRS119
           MOVE GDA-DATA-ATUAL         TO LK82-DT-EFT-TRAN                VRS119
                                          LK82-DT-MVT-CT-CRT.             VRS119
           MOVE WDESCRICAO             TO LK82-TX-MVT-CT-CRT.             VRS119
      *****************************************************************   VRS119
      ***  Atencao: O valor do movimento de anuidade eh gravado a   ***   VRS119
      ***           da variavel CONTAS-VL-PCL-ANUD                  ***   VRS119
      *****************************************************************   VRS119
           MOVE GDA-VL-ESTN-DAA        TO LK82-VL-MOE-OGNL-MVT            VRS119
                                          GDA-VL-DSC-PORT                 VRS119
                                          LK82-VL-MVT-CT-CRT.             VRS119
           MOVE 21                     TO LK82-CD-PLN-VIP.                VRS119
           MOVE 'ANU'                  TO LK82-SG-SSIS-OGM.               VRS119
           MOVE 613000                 TO LK82-CD-TRAN.                   VRS119
           MOVE 1001                   TO LK82-CD-DET-TRAN.               VRS119
           MOVE '2'                    TO LK82-IN-PSTG.                   VRS119
           MOVE '986'                  TO LK82-CD-MOE-OGNL.               VRS119
           MOVE 100                    TO LK82-CD-ORG.                    VRS119
           MOVE SPACES                 TO LK82-CD-AUTZ-TRAN               VRS119
                                          LK82-CD-MDU-PRCR                VRS119
                                          LK82-CD-ITCB-CRT.               VRS119
           MOVE 'VIPP0007'             TO LK82-CD-USU-RSP-LCTO.           VRS119
           MOVE CONTAS-CD-MDLD-CRT     TO LK82-NR-TIP-MDLD.               VRS119
           MOVE ZEROS                  TO LK82-NR-CMPT-PLST               VRS119
                                          LK82-VL-US-MVT-CT-CRT           VRS119
                                          LK82-NR-CTR-NEGO                VRS119
                                          LK82-NR-TIP-PROD                VRS119
                                          LK82-NR-CD-DEPE                 VRS119
                                          LK82-IND-ERRO                   VRS119
                                          LK82-EIBRESP                    VRS119
                                          LK82-NR-PCL-MVT-CPR             VRS119
                                          LK82-QT-PCL-MVT-CPR             VRS119
                                          LK82-VL-CNV-DT-CPR              VRS119
                                          LK82-NR-IDFR-TRAN-C.            VRS119
           MOVE 'S'                    TO LK82-IND-TIPO-COMP.             VRS119

           PERFORM 14600-00-BUSCA-REFNUMBER.                              VRS119

           CALL VIPP0082 USING LK82-MVT-PARAM.                            VRS119

           IF  LK82-IND-ERRO NOT EQUAL ZEROS                              VRS119
               DISPLAY LK82-RETORNO                                       VRS119
               DISPLAY LK82-DESCRICAO-1                                   VRS119
               DISPLAY LK82-DESCRICAO-2                                   VRS119
               DISPLAY LK82-SQLCODE                                       VRS119
               DISPLAY LK82-SQLCODE-COMP                                  VRS119
               MOVE LK82-SQLCODE       TO GDA-CODESQL                     VRS119
                                          SQLCODE                         VRS119
               DISPLAY 'Erro Programa VIPP0082 - ' GDA-CODESQL            VRS119
               PERFORM 90010-00-MENSAGEM-ERRO-001.                        VRS119

           ADD 1                       TO WCOMMIT                         VRS119
                                          WGRAVADOS.                      VRS119
      * botar END-IF  <<<
           IF  WCOMMIT GREATER 10                                         VRS119
               MOVE GDA-DATA-VIP7      TO 207-VL-TIP-DT                   VRS119
               MOVE GDA-CTRL-CICLO     TO 207-QT-DCML                     VRS119
               PERFORM 14500-00-ATUALIZA-LIDER                            VRS119
               MOVE 'COMMIT PARCIAL'   TO GDA-CURSOR                      VRS119
               EXEC SQL                                                   VRS119
                    COMMIT                                                VRS119
               END-EXEC                                                   VRS119
               IF SQLCODE NOT EQUAL ZEROS                                 VRS119
                  PERFORM 90010-00-MENSAGEM-ERRO-001                      VRS119
               END-IF                                                     VRS119
               MOVE ZEROS              TO WCOMMIT                         VRS119
           END-IF.                                                        VRS119

           PERFORM 290000-00-GRAVA-MVT-ANUD.                              VRS119
           PERFORM 14000-02-INSERT-TAB-DAA.                               VRS119
      *                                                                   VRS119
           EXEC SQL                                                       VRS119
                UPDATE DB2VIP.PORT_CRT                                    VRS119
                   SET VL_ANUD_FATD      = VL_ANUD_FATD                   VRS119
                                         - :GDA-VL-ESTN-DAA               VRS119
                 WHERE NR_CT_CRT         = :CONTAS-NR-CT-CRT              VRS119
                   AND NR_SEQL_TITD_PORT = :CONTAS-NR-SEQL-TITD-PORT      VRS119
           END-EXEC.                                                      VRS119
      *                                                                   VRS119
           IF SQLCODE NOT EQUAL ZEROS                                     VRS119
              PERFORM 90010-00-MENSAGEM-ERRO-001                          VRS119
           END-IF.                                                        VRS119

       27500-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS119
       280000-00-GRAVA-VIPFSANU            SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           INITIALIZE VIPKCONF
           MOVE CONTAS-NR-CT-CRT            TO VIPKCONF-NR-CRT
           MOVE CONTAS-NR-SEQL-TITD-PORT    TO VIPKCONF-SEQ-TIT
           MOVE 904-DT-PRI-COMPRA           TO VIPKCONF-DT-PRI-COMPRA
      *                                                                   VRS115
           WRITE FD-REG-VIPFSANU          FROM  VIPKCONF.
      *                                                                   VRS115
       28000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       290000-00-GRAVA-MVT-ANUD            SECTION.
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
           MOVE  CONTAS-NR-CT-CRT      TO VIPKANUD-NR-CT-CRT.
           MOVE  CONTAS-CD-MDLD-CRT    TO VIPKANUD-CD-MDLD-CRT.
           MOVE  CONTAS-NR-PLST        TO VIPKANUD-NR-PLST.
           MOVE  GDA-DATA-ATUAL        TO VIPKANUD-DATA-ATUAL.
           MOVE  WDESCRICAO            TO VIPKANUD-DESCRICAO.
           MOVE  LK82-CD-TRAN          TO VIPKANUD-CD-TRAN.
           MOVE  LK82-VL-MOE-OGNL-MVT  TO VIPKANUD-VL-PCL-ANUD
           MOVE  CONTAS-CD-CLI         TO VIPKANUD-CD-CLIENTE             VRS128
           MOVE  CONTAS-NR-SEQL-TITD-PORT                                 VRS128
                                       TO VIPKANUD-NR-SEQL-TITD           VRS128
           ADD   1                     TO GDA-REG-GRAV-ANUD.

           WRITE FD-REG-VIPFANUD          FROM  VIPKANUD.
      *                                                                   VRS115
       29000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS115
       30000-00-FINALIZA-REFNUMBER     SECTION.
      *----------------------------------------------------------------*  VRS115

           MOVE  GDA-SEQL-REFNUM       TO 207-VL-TIP-NR.
           MOVE  'ANU'                 TO 207-CD-SIST.
           MOVE  'REFNUMAN'            TO 207-NM-PRM.

           EXEC  SQL
                 UPDATE DB2VIP.LIDER
                    SET VL_TIP_NR = :207-VL-TIP-NR
                  WHERE CD_SIST = :207-CD-SIST  AND
                        NM_PRM  = :207-NM-PRM
           END-EXEC.

           IF  SQLCODE NOT EQUAL ZEROS
               PERFORM 90060-00-MENSAGEM-ERRO-006
           END-IF.

       30000-99-EXIT.
           EXIT.
      *----------------------------------------------------------------*  VRS121
       31000-00-MONTA-TAB-EXCO         SECTION.                           VRS121
      *----------------------------------------------------------------*  VRS121
      *
           EXEC SQL                                                       VRS121
                FETCH   GREXCO                                            VRS121
                  INTO :GREXCO-CD-MDLD-CRT                                VRS121
           END-EXEC.                                                      VRS121
      *
           EVALUATE SQLCODE                                               VRS121
             WHEN 0                                                       VRS121
                  MOVE GREXCO-CD-MDLD-CRT   TO  TAB-CD-MDLD-EXCO(WIND)    VRS121
             WHEN +100                                                    VRS121
                  MOVE 'S'  TO IN-FIM-EXCO                                VRS121
             WHEN OTHER                                                   VRS121
                  PERFORM 90010-00-MENSAGEM-ERRO-001                      VRS121
           END-EVALUATE.                                                  VRS121
      *
       31000-99-EXIT.                                                     VRS121
           EXIT.                                                          VRS121
      *
      *----------------------------------------------------------------*  VRS134
       32000-00-MONTA-TAB-S1VIP0A1     SECTION.                           VRS134
      *----------------------------------------------------------------*
      *
      * MOCK-POINT FORCA-ERRO-009
      *
           MOVE CONTAS-NR-CT-CRT        TO 0A1-NR-CT-CRT.
           MOVE CONTAS-NR-SEQL-TITD-PORT
                                        TO 0A1-NR-SEQL-TITD-PORT.
           MOVE 'INV'                   TO 0A1-SG-TIP-DSC.
           MOVE 904-PC-GSTO             TO 0A1-PC-LIM-CON.
           MOVE 904-PC-INV-CLI          TO 0A1-PC-LIM-INVS.
           MOVE 904-VL-GSTO             TO 0A1-VL-SDO-GSTO.
           MOVE 904-VL-INV-CLI          TO 0A1-VL-INVS-CLI.

           IF  904-PC-INV-CLI EQUAL 100
               ADD 1               TO CNT-PORT-INV-ATDG
           ELSE
               ADD 1               TO CNT-PORT-INV-N-ATDG
           END-IF

           EXEC SQL
              INSERT INTO DB2VIP.APL_DSC_AUTC_ANUD
                 (NR_CT_CRT,
                 NR_SEQL_TITD_PORT,
                 TS_APL_DSC_AUTC,
                 SG_TIP_DSC,
                 PC_LIM_CON,
                 PC_LIM_INVS,
                 PC_DSC_ATBD,
                 VL_SDO_GSTO,
                 VL_INVS_CLI)
                 VALUES
                 (:0A1-NR-CT-CRT        ,
                  :0A1-NR-SEQL-TITD-PORT,
                   CURRENT_TIMESTAMP    ,
                  :0A1-SG-TIP-DSC       ,
                  :0A1-PC-LIM-CON       ,
                  :0A1-PC-LIM-INVS      ,
                  :0A1-PC-DSC-ATBD      ,
                  :0A1-VL-SDO-GSTO      ,
                  :0A1-VL-INVS-CLI)
           END-EXEC.
      *
           IF SQLCODE NOT EQUAL 0 AND NOT EQUAL +100
              PERFORM 90100-00-MENSAGEM-ERRO-010
           END-IF.
      *                                                                   VRS134
       32000-99-EXIT.                                                     VRS134
           EXIT.                                                          VRS134
      *
      ******************************************************************  VRS115
      ********       Mensagens de erros e cancelamentos         ********  VRS115
      ******************************************************************  VRS115

       90010-00-MENSAGEM-ERRO-001      SECTION.

           MOVE SQLCODE                TO GDA-CODESQL.

           DISPLAY '001 ' CTE-PROG ' - CT CARTAO: ' CONTAS-NR-CT-CRT.
           DISPLAY '001 ' CTE-PROG ' - ' GDA-MENSAGEM-SQL01.
           DISPLAY '001 ' CTE-PROG ' - ' GDA-MENSAGEM-SQL02.
           DISPLAY '001 ' CTE-PROG ' - ' CONTAS-DT-PRX-ANIV-ANUD
           DISPLAY '001 ' CTE-PROG ' - ' GDA-DATA-ATUAL
           DISPLAY '001 ' CTE-PROG ' - ' CONTAS-DT-PRMO-CBR-ANUD
           DISPLAY '001 ' CTE-PROG ' - ' ARG01
           DISPLAY '001 ' CTE-PROG ' - ' ARG02
           DISPLAY '001 ' CTE-PROG ' - ' ARG03

           PERFORM 99000-00-SAIDA.

       90010-99-EXIT.
           EXIT.

       90030-00-MENSAGEM-ERRO-003      SECTION.

           MOVE SQLCODE                TO GDA-CODESQL.

           DISPLAY '002 ' CTE-PROG ' - Erro na SBDATA ' ARG01.
           DISPLAY '002 ' CTE-PROG ' - ' GDA-MENSAGEM-SQL02.

           PERFORM 99000-00-SAIDA.

       99030-99-EXIT.
           EXIT.

       90040-00-MENSAGEM-ERRO-004      SECTION.

           MOVE SQLCODE                TO GDA-CODESQL.

           DISPLAY '003 ' CTE-PROG ' - Erro na busca data proc.'.
           DISPLAY '003 ' CTE-PROG ' - ' GDA-MENSAGEM-SQL02.

           PERFORM 99000-00-SAIDA.

       99040-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90050-00-MENSAGEM-ERRO-005      SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 005 ************************'
           DISPLAY '005 ' CTE-PROG ' - SELECT NA TABELA LIDER'
           DISPLAY '005 ' CTE-PROG ' - Captura sequencial Refnumber'
           DISPLAY '005 ' CTE-PROG ' - sql: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       99050-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90060-00-MENSAGEM-ERRO-006      SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 006 ************************'
           DISPLAY '006 ' CTE-PROG ' - UPDATE NA TABELA LIDER'
           DISPLAY '006 ' CTE-PROG ' - ATUALIZA SEQUENCIAL REFNUMBER'
           DISPLAY '006 ' CTE-PROG ' - SQL: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       99060-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90070-00-MENSAGEM-ERRO-007      SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 007 ************************'
           DISPLAY '007 ' CTE-PROG ' - BUSCA ANUIDADE PADRAO DA MDLD'
           DISPLAY '007 ' CTE-PROG ' - CTA : ' CONTAS-NR-CT-CRT
           DISPLAY '007 ' CTE-PROG ' - TITD: ' CONTAS-NR-SEQL-TITD-PORT
           DISPLAY '007 ' CTE-PROG ' - MDLD: ' CONTAS-CD-MDLD-CRT.
           DISPLAY '007 ' CTE-PROG ' - sql: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       99070-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90080-00-MENSAGEM-ERRO-008      SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 008 ************************'
           DISPLAY '008 ' CTE-PROG ' - BUSCA PARCELAS ANUIDADE PADRAO'
           DISPLAY '008 ' CTE-PROG ' - DA MODALIDADE'
           DISPLAY '008 ' CTE-PROG ' - CTA : ' CONTAS-NR-CT-CRT
           DISPLAY '008 ' CTE-PROG ' - TITD: ' CONTAS-NR-SEQL-TITD-PORT
           DISPLAY '008 ' CTE-PROG ' - MDLD: ' CONTAS-CD-MDLD-CRT.
           DISPLAY '008 ' CTE-PROG ' - ANUD: ' GDA-CD-ANUD-PDAO-I2.
           DISPLAY '008 ' CTE-PROG ' - sql: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       99070-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90090-00-MENSAGEM-ERRO-009      SECTION.                           VRS133
      *
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 009 ************************'
           DISPLAY '009 ' CTE-PROG '009 - ERRO NA SUBROTINA SBCPU '.
           DISPLAY '009 ' CTE-PROG '009 - RET.CODE : ' RETURN-CODE.
           DISPLAY '009 ' CTE-PROG '009 - CPU-NOME : ' NOME-CPU.
           PERFORM 99000-00-SAIDA.
      *
       99090-99-EXIT.
           EXIT.
      *
       90100-00-MENSAGEM-ERRO-010      SECTION.
      *                                                                   VRS134
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 010 ************************'
           DISPLAY '008 ' CTE-PROG ' - INSERT TAB APL_DSC_AUTC_ANUD'
           DISPLAY '008 ' CTE-PROG ' - CTA : ' CONTAS-NR-CT-CRT
           DISPLAY '008 ' CTE-PROG ' - TITD: ' CONTAS-NR-SEQL-TITD-PORT
           DISPLAY '008 ' CTE-PROG ' - sql: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS134
       99100-99-EXIT.
           EXIT.
      *                                                                   VRS133
       999015-ERRO-15.
      *------------------------------------------------------------*      VRS115
           DISPLAY '888 ' CTE-PROG '015 - ERRO CALL VIPSB957'.
           DISPLAY '888 ' CTE-PROG '015 - CONTA CARTAO...:  '
                                          CONTAS-NR-CT-CRT.
           DISPLAY '888 ' CTE-PROG '015 - KS957-NR-CT-CRT-F01 '
                                          KS957-NR-CT-CRT-F01
           DISPLAY '888 ' CTE-PROG '015 - KS957-COD-RET  = '
                                          KS957-COD-RET.
           DISPLAY '888 ' CTE-PROG '015 - KS957-SEQ-RET  = '
                                          KS957-SEQ-RET.
           DISPLAY '888 ' CTE-PROG '015 - KS957-TXT-RET  = '
                                          KS957-TXT-RET.
           MOVE  KS957-SQLCODE         TO GDA-CODESQL.
           DISPLAY '888 ' CTE-PROG '015 - KS957-SQLCODE  = '
                                          GDA-CODESQL.
           DISPLAY '888 ' CTE-PROG '015 - KS957-NOM-PGM  = '
                                          KS957-NOM-PGM.
           PERFORM 99000-00-SAIDA.

       999016-ERRO-16.
      *------------------------------------------------------------*      VRS115
           DISPLAY '888 ' CTE-PROG '016 - ERRO CALL VIPSB958 '.
           DISPLAY '888 ' CTE-PROG '016 - KS958-INPUT-SGL-SIS = '
                                          KS958-INPUT-SGL-SIS.
           DISPLAY '888 ' CTE-PROG '016 - KS958-INPUT-PRF-AGE = '
                                          KS958-INPUT-PRF-AGE.
           DISPLAY '888 ' CTE-PROG '016 - KS958-COD-RET  = '
                                          KS958-COD-RET.
           DISPLAY '888 ' CTE-PROG '016 - KS958-SEQ-RET  = '
                                          KS958-SEQ-RET.
           DISPLAY '888 ' CTE-PROG '016 - KS958-TXT-RET  = '
                                          KS958-TXT-RET.
           MOVE  KS958-SQLCODE         TO GDA-CODESQL.
           DISPLAY '888 ' CTE-PROG '016 - KS958-SQLCODE  = '
                                          GDA-CODESQL.
           DISPLAY '888 ' CTE-PROG '016 - KS958-NOM-PGM  = '
                                          KS958-NOM-PGM.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
       999017-ERRO-17.
      *------------------------------------------------------------*      VRS115
           DISPLAY '888 ' CTE-PROG '017 --------------------------'.
           DISPLAY '888 ' CTE-PROG '017 - ERRO CALL VIPP0082 '.
           DISPLAY '888 ' CTE-PROG '017 --------------------------'.
           DISPLAY '888 ' CTE-PROG '017 LK82-NR-CT-CRT       : '
                                          LK82-NR-CT-CRT.
           DISPLAY '888 ' CTE-PROG '017 LK82-NR-PLST         : '
                                          LK82-NR-PLST.
           DISPLAY '888 ' CTE-PROG '017 LK82-DT-EFT-TRAN     : '
                                          LK82-DT-EFT-TRAN
           DISPLAY '888 ' CTE-PROG '017 LK82-DT-MVT-CT-CRT   : '
                                          LK82-DT-MVT-CT-CRT.
           DISPLAY '888 ' CTE-PROG '017 LK82-TX-MVT-CT-CRT   : '
                                          LK82-TX-MVT-CT-CRT.
           DISPLAY '888 ' CTE-PROG '017 LK82-VL-MOE-OGNL-MVT : '
                                          LK82-VL-MOE-OGNL-MVT
           DISPLAY '888 ' CTE-PROG '017 LK82-NR-CTL-SSIS-OGM : '
                                          LK82-NR-CTL-SSIS-OGM.
           DISPLAY '888 ' CTE-PROG '017 LK82-NR-TIP-MDLD     : '
                                          LK82-NR-TIP-MDLD.
           DISPLAY '888 ' CTE-PROG '017 --------------------------'.
           DISPLAY '888 - 017 - LK82-RETORNO    : ' LK82-RETORNO.
           DISPLAY '888 - 017 - LK82-DESCRICAO-1: ' LK82-DESCRICAO-1.
           DISPLAY '888 - 017 - LK82-DESCRICAO-2: ' LK82-DESCRICAO-2.
           MOVE LK82-SQLCODE                TO GDA-CODESQL.
           DISPLAY '888 - 017 - LK82-SQLCODE    : ' GDA-CODESQL.
      *                                                                   VRS115
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       999018-ERRO-18          SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 018 ************************'
           DISPLAY '888 - 018 ' CTE-PROG ' - SUB_MDLD_GR'
           DISPLAY '888 - 018 ' CTE-PROG ' - BUSCA GRUPO DAA'
           DISPLAY '888 - 018 ' CTE-PROG ' - SQL: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
      *                                                                   VRS115
       999018-ERRO-19          SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 019 ************************'
           DISPLAY '888 - 019 ' CTE-PROG ' - PORT-CRT'
           DISPLAY '888 - 019 ' CTE-PROG ' - BUSCA SUB TIT DAA'
           DISPLAY '888 - 019 ' CTE-PROG ' - SQL: ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *
       999020-ERRO-20          SECTION.
      *
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 020 ************************'
           DISPLAY '272000-00-RECUPERA-DESC-MCI'
           DISPLAY 'CALL VIPST05V'
           DISPLAY ' '
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-CD-ERRO.........: '
                                              VIPST05V-CD-ERRO
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-CD-SQLCODE......: '
                                              VIPST05V-CD-SQLCODE
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-MSG-ERRO........: '
                                              VIPST05V-MSG-ERRO
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-FUNCAO..........: 2'
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-NR-CT-CRT.......: '
                                              CONTAS-NR-CT-CRT
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-PC-DSC-MSLD.....: 0'
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-VL-DSC-MSLD.....: 0'
           DISPLAY '888 ' CTE-PROG ' - VIPST05V-DT-FIM-VGC-DSC..: SPACE'
      *
           PERFORM 99000-00-SAIDA.
      *
       99060-99-EXIT.
           EXIT.
      *                                                                   VRS115
       90070-00-MENSAGEM-ERRO-021      SECTION.
      *                                                                   VRS115
           MOVE SQLCODE                TO GDA-CODESQL.
           DISPLAY '**************** ERRO 021 ************************'
           DISPLAY '007 ' CTE-PROG ' - BUSCA ANUIDADE PADRAO DA MDLD'
           DISPLAY '007 ' CTE-PROG ' - POR SUB MDLD                 '
           DISPLAY '007 ' CTE-PROG ' - CTA : ' CONTAS-NR-CT-CRT
           DISPLAY '007 ' CTE-PROG ' - TITD: ' CONTAS-NR-SEQL-TITD-PORT
           DISPLAY '007 ' CTE-PROG ' - MDLD: ' CONTAS-CD-MDLD-CRT.
           DISPLAY '007 ' CTE-PROG ' - SUB : ' GDA-SUB-MDLD
           DISPLAY '007 ' CTE-PROG ' - SQL:  ' GDA-CODESQL.
           PERFORM 99000-00-SAIDA.
      *                                                                   VRS115
       99070-99-EXIT.
           EXIT.
      *
      *----------------------------------------------------------------*  VRS115
      *                                                                   VRS115
       99000-00-SAIDA                  SECTION.
      *----------------------------------------------------------------*  VRS115

      *    COPYBOOK ERRO SQL                                              VRS115
-INC  DBUD0000

           DISPLAY '999 ' CTE-PROG ' ******* Cancelado *******'.

           EXEC SQL
                ROLLBACK
           END-EXEC.

           IF SQLCODE NOT EQUAL ZEROS
              MOVE SQLCODE             TO GDA-CODESQL
              DISPLAY '999 ' CTE-PROG ' Erro no ROLLBACK '
                   GDA-CODESQL
           END-IF.
           .

      ***  -INC CCS507                                                    VRS115
           COPY CCS507.

      ***  -INC CCS502                                                    VRS115
           COPY CCS502.

           ADD  1 TO  CNT-ERRO-DB2.
           IF  CNT-ERRO-DB2 > 100
               CALL 'SBABEND'
           END-IF.

       99000-99-EXIT.
           EXIT.
      ******************************************************************  VRS115
      ****************     Fim do programa VIPP0007    *****************  VRS115
      ******************************************************************  VRS115