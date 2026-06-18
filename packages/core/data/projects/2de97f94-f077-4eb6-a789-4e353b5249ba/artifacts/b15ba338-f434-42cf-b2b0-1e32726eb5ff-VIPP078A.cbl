000060******************************************************************
       IDENTIFICATION DIVISION.
000020 PROGRAM-ID.  VIPP078A.
000060******************************************************************
000070*                                                                *
000120*   SUBROTINA PARA DETERMINACAO DE CODIGO DE ANUIDADE.           *
000130*                                                                *
000130*   OBS: FOI USADO A VIPP0078 COMO MODELO                        *
000130*        (DIFERENCIANDO O TRATAMENTO POR SUB-MDLD)               *
000130*                                                                *
000170******************************************************************

       ENVIRONMENT DIVISION.
000200 CONFIGURATION SECTION.
000210 SOURCE-COMPUTER.         IBM-4331.
000220 OBJECT-COMPUTER.         IBM-4331.
       DATA DIVISION.
000240
000250 WORKING-STORAGE SECTION.
      *                                                                   VRS069
000252 77  CTE-INICIO                        PIC X(30) VALUE
000253     'VIPP078A  - W.S.S. COMECA AQUI'.
000254 77  CTE-PROG                          PIC X(16) VALUE
000255     '*** VIPP078A ***'.
000256 77  CTE-VERS                          PIC X(06) VALUE 'VRS004'.    VRS006
000257 77  SBVERSAO                          PIC X(08) VALUE 'SBVERSAO'.
      *                                                                   VRS099
       77  VIPST752                          PIC X(08) VALUE 'VIPST752'.
      *
       LOCAL-STORAGE SECTION.
000270 01  WS-BB-AREA-TRABALHO.
000290     05  WS-BB-SQLCODE-RESP      PIC ---9.
000300     05  WS-BB-SQLCODE-RESP-R  REDEFINES  WS-BB-SQLCODE-RESP
000310                                 PIC X(04).

000330     05  WS-BB-CD-MDLD-CRT-CRD   PIC 9(07)            VALUE ZEROS.
000340     05  WS-BB-REG-LIDOS         PIC S9(07)    COMP-3 VALUE ZEROS.
000350     05  WS-BB-NR-PRIO-ANUD      PIC S9(05)    COMP-3 VALUE ZEROS.
000360     05  WS-BB-NOT-NULL-CD-MDU   PIC S9(04)    COMP.
000370     05  WS-BB-NOT-NULL-NR-PRIO  PIC S9(04)    COMP.
000380     05  WS-BB-NOT-NULL-VLD-AN   PIC S9(04)    COMP.
000390     05  WS-BB-NOT-NULL-CAR-AN   PIC S9(04)    COMP.
000391     05  WS-BB-NOT-NULL-NVL-ACSS PIC S9(04)    COMP.
000400     05  WS-BB-NOT-NULL          PIC S9(04)    COMP.
000401     05  WS-BB-TAB-ANUIDADE      PIC X(121).
000420     05  WS-BB-QT-AA-VLD-ANUD    PIC 9(05).
000430     05  WS-BB-QT-AA-CARE-ANUD   PIC 9(05).
000440     05  WS-BB-CD-ANUD           PIC 9(05).
000441     05  WS-BB-CD-OCI            PIC 9(05).
000442     05  WS-BB-VL-DSC-ANUD       PIC S9(5)V9(2) COMP-3.
000443     05  WS-BB-MENSAGEM-ERRO.
000444         10  FILLER              PIC X(25)   VALUE
000445             'CONTA C/ MAIS CODIGO OCI '.
000446         10  WS-BB-MENS-CD-OCI-01 PIC X(05)B.
000447         10  WS-BB-MENS-CD-OCI-02 PIC X(05)B.
000448         10  WS-BB-MENS-CD-OCI-03 PIC X(05)B.
000449         10  WS-BB-MENS-CD-OCI-04 PIC X(05)B.

000531     05  TABELA-COD-OCI.
000532         10  TAB-BB-CD-OCI-01  OCCURS  4 TIMES
000533                              INDEXED  BY  WIN-OCI.
000534             15  TB-BB-CD-ANUD       PIC 9(05).

000590 01  WS-BB-PARAMETROS.
000610     05  WS-BB-NR-CT-CRT         PIC 9(09)B.
000620     05  WS-BB-NR-SEQL-TITD-PORT PIC 9(09).

000631 01  WS-BB-ANUD-PDRAO-MDLD       PIC S9(9) USAGE COMP.

000631 01  GDA-ANUD-PADRAO             PIC S9(9) USAGE COMP.

       01  IND-DSC-SUB                 PIC  X(001)    VALUE SPACES.

000640 01  WS-BB-FLAG-LEITURA          PIC X       VALUE SPACES.

000660 01  WS-BB-FLAG-FINALIZACAO      PIC X       VALUE SPACES.

000631 01  GDA-ANUD-PDRAO-MDLD       PIC S9(9) USAGE COMP.

       01  PARM-VIPST752.
-INC  VIPKT752

-INC  VIPK101D                                                          00000680
000690
-INC  VIPK140D                                                          00000700
000710
-INC  VIPK164D                                                          00000720

-INC  VIPK166D                                                          00000740

-INC  VIPK748D

-INC HLPKDFHE


           EXEC SQL
000752          INCLUDE SQLCA
           END-EXEC.

           EXEC SQL
000772          DECLARE CRSPORT CURSOR FOR
000773           SELECT CD_ANUD
000774                , QT_AA_VLD_ANUD
000775                , QT_AA_CARE_ANUD
000776                , IN_DSC_ANUD
000777                , VL_DSC_ANUD
000778                , DT_FIM_CD_ANUD
                   FROM DB2VIP.ANUD_PORT
000780            WHERE NR_CT_CRT         = :166-NR-CT-CRT
000781              AND NR_SEQL_TITD_PORT = :166-NR-SEQL-TITD-PORT
           END-EXEC.

000870 LINKAGE SECTION.

000890 01  LK-PARAMETROS-AGRUP.
000910     05  LK-BB-NR-CT-CRT         PIC S9(17) USAGE COMP-3.
000920     05  LK-BB-NR-SEQL-TITD-PORT PIC S9(09) USAGE COMP-3.
000920     05  LK-BB-CD-SUB-MDLD-CRT   PIC S9(04) COMP.
000920     05  LK-BB-IN-GR-158         PIC  X(01).
000921     05  LK-BB-TAB-ANUIDADE      PIC  X(121).
      *         07 LK-BB-CD-ANUD              PIC S9(4) USAGE COMP.
      *         07 LK-BB-IN-CBR-PRO-RATD      PIC X(1).
      *         07 LK-BB-IN-CBR-APVC-DEB      PIC X(1).
      *         07 LK-BB-DT-INC-VGC           PIC X(10).
      *         07 LK-BB-DT-FIM-VGC           PIC X(10).
      *         07 LK-BB-VL-PCL-TIT          PIC S9(9)V9(2) USAGE COMP-3.
      *         07 LK-BB-VL-PCL-ADC          PIC S9(9)V9(2) USAGE COMP-3.
      *         07 LK-BB-QT-PCL-TIT           PIC S9(4) USAGE COMP.
      *         07 LK-BB-QT-PCL-ADC           PIC S9(4) USAGE COMP.
      *         07 LK-BB-TX-ANUD              PIC X(70).
      *         07 LK-BB-CD-MDU-LGC           PIC S9(4) USAGE COMP.
      *         07 LK-BB-NR-PRIO-ANUD         PIC S9(4) USAGE COMP.
      *         07 LK-BB-QT-AA-VLD-ANUD-A       PIC S9(4) USAGE COMP.
      *         07 LK-BB-QT-AA-CARE-ANUD-A      PIC S9(4) USAGE COMP.
      *         07 LK-BB-CD-NVL-ACSS          PIC S9(4) USAGE COMP.
      *         07 LK-BB-IN-ISN-ANUD          PIC  X(1).
000940     05  LK-BB-QT-AA-VLD-ANUD    PIC S9(05) USAGE COMP-3.
000950     05  LK-BB-QT-AA-CARE-ANUD   PIC S9(05) USAGE COMP-3.
000951     05  LK-BB-CODIGO-OCI        PIC S9(05) USAGE COMP-3.

-INC  VIPK081W                                                          00000980

001000 PROCEDURE DIVISION  USING  LK-PARAMETROS-AGRUP.
001630*-----------------------------------------------

001011     MOVE ALL SPACES             TO  WS-BB-TAB-ANUIDADE
001012                                     GDA-DADOS-ERRO
001013                                     WS-BB-FLAG-FINALIZACAO
001014                                     WS-BB-FLAG-LEITURA
001015                                     WS-BB-MENS-CD-OCI-01
001016                                     WS-BB-MENS-CD-OCI-02
001017                                     WS-BB-MENS-CD-OCI-03
001018                                     WS-BB-MENS-CD-OCI-04.
001019     MOVE ALL ZEROS              TO  TABELA-COD-OCI
001020                                     WS-BB-QT-AA-VLD-ANUD
001021                                     WS-BB-QT-AA-CARE-ANUD
001022                                     WS-BB-CD-ANUD
001023                                     WS-BB-CD-OCI
001024                                     WS-BB-REG-LIDOS
001025                                     WS-BB-NR-PRIO-ANUD
001026                                     WS-BB-VL-DSC-ANUD
                                           LK-BB-QT-AA-VLD-ANUD
                                           LK-BB-QT-AA-CARE-ANUD
                                           LK-BB-CODIGO-OCI
001027                                     IND-ERRO.
001171     SET   WIN-OCI               TO  1.
001172     SET   WIN-OCI  DOWN  BY  1.

001210     IF  LK-BB-NR-CT-CRT  NOT NUMERIC
001220         MOVE  '0001'            TO  GDA-LOCAL
001230         MOVE  1                 TO  IND-ERRO
001240         MOVE  'VIPP078A'        TO  GDA-PROG-ERRO
001250         MOVE  'NUMERO CONTA INVALIDO'
001260                                 TO  GDA-DESCRICAO-1
001270         PERFORM 9000-10-RETORNO
001280     END-IF

001300     IF  LK-BB-NR-SEQL-TITD-PORT  NOT NUMERIC
001310         MOVE  '0002'            TO  GDA-LOCAL
001320         MOVE  1                 TO  IND-ERRO
001330         MOVE  'VIPP078A'        TO  GDA-PROG-ERRO
001340         MOVE  'CODIGO TITULARIDADE INVALIDO'
001350                                 TO  GDA-DESCRICAO-1
001360         PERFORM 9000-10-RETORNO
001370     END-IF

001381     MOVE  LK-BB-NR-CT-CRT       TO  WS-BB-NR-CT-CRT
001382                                     166-NR-CT-CRT.
001383     MOVE  LK-BB-NR-SEQL-TITD-PORT  TO  WS-BB-NR-SEQL-TITD-PORT
001384                                        166-NR-SEQL-TITD-PORT.
001410     MOVE  WS-BB-PARAMETROS      TO  GDA-DESCRICAO-2.

001450     PERFORM  8000-PESQUISA-CONTA-PARAM
001451        THRU  8000-99-EXIT.

           EXEC  SQL
001454           OPEN  CRSPORT
           END-EXEC.

001480     IF  SQLCODE  NOT EQUAL  ZEROS
001490         MOVE  '0003'            TO  GDA-LOCAL
001500         MOVE  1                 TO  IND-ERRO
001510         MOVE  'VIPP078A'        TO  GDA-PROG-ERRO
001520         MOVE  'OPEN DB2VIP.ANUD-PORT CURSOR CRSPORT'
001530                                 TO  GDA-DESCRICAO-1
001531         MOVE  SQLCODE           TO  WS-BB-SQLCODE-RESP
001550         MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
001560         PERFORM 9000-10-RETORNO
           END-IF.

001590     MOVE  '*'                   TO WS-BB-FLAG-LEITURA.

001600     GO TO 2000-LEITURA-TABELA-ANUIDADE.

001620 1000-LEITURA-TABELA-AGRUP.
001630*--------------------------
           EXEC  SQL
001642           FETCH  CRSPORT
001643            INTO  :166-CD-ANUD
001644               ,  :166-QT-AA-VLD-ANUD
001645               ,  :166-QT-AA-CARE-ANUD
001646               ,  :166-IN-DSC-ANUD
001647               ,  :166-VL-DSC-ANUD
001648               ,  :166-DT-FIM-CD-ANUD
           END-EXEC.

001700     IF  SQLCODE  IS NOT EQUAL  ZEROS
001710         IF  SQLCODE  IS NOT EQUAL  +100
001711             MOVE  '0004'        TO  GDA-LOCAL
001712             MOVE  1             TO  IND-ERRO
001713             MOVE  'VIPP078A'    TO  GDA-PROG-ERRO
001750             MOVE  'FETCH DB2VIP.ANUD_PORT'
001760                                 TO  GDA-DESCRICAO-1
001770             MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
001780             MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
001790             PERFORM 9000-10-RETORNO
001800         ELSE
001810             MOVE  WS-BB-TAB-ANUIDADE    TO  LK-BB-TAB-ANUIDADE
001820             MOVE  WS-BB-QT-AA-VLD-ANUD  TO  LK-BB-QT-AA-VLD-ANUD
001830             MOVE  WS-BB-QT-AA-CARE-ANUD TO  LK-BB-QT-AA-CARE-ANUD
001831             MOVE  TB-BB-CD-ANUD (01)    TO  LK-BB-CODIGO-OCI
001832             IF  WS-BB-VL-DSC-ANUD  NOT EQUAL  ZEROS
001833                 IF  WS-BB-VL-DSC-ANUD GREATER
001834                                       WS-BB-ANUD-PDRAO-MDLD
001835                     MOVE ZEROS          TO  LK-BB-CODIGO-OCI
001836                 ELSE
001837                     IF  WS-BB-VL-DSC-ANUD  EQUAL
001838                                       WS-BB-ANUD-PDRAO-MDLD
001839                         MOVE 100        TO  LK-BB-CODIGO-OCI
001840                     ELSE
001841                         COMPUTE WS-BB-CD-OCI =
001842                           ((WS-BB-VL-DSC-ANUD /
001843                             WS-BB-ANUD-PDRAO-MDLD) + 1) * 100
001844                         MOVE WS-BB-CD-OCI  TO  LK-BB-CODIGO-OCI
001845                     END-IF
001862                 END-IF
001863             END-IF
001864             IF  TB-BB-CD-ANUD (01)  IS NOT EQUAL TO  ZEROS  AND
001865                 TB-BB-CD-ANUD (02)  IS NOT EQUAL TO  ZEROS
001866                 MOVE  '0005'            TO  GDA-LOCAL
001867                 MOVE  1                 TO  IND-ERRO
001868                 MOVE  'VIPP078A'        TO  GDA-PROG-ERRO
001869                 MOVE  TB-BB-CD-ANUD (01) TO  WS-BB-MENS-CD-OCI-01
001870                 MOVE  TB-BB-CD-ANUD (02) TO  WS-BB-MENS-CD-OCI-02
001871                 IF  TB-BB-CD-ANUD (03) IS NOT EQUAL TO  ZEROS
001872                     MOVE  TB-BB-CD-ANUD (03)
001873                                          TO  WS-BB-MENS-CD-OCI-03
001874                 END-IF
001875                 IF  TB-BB-CD-ANUD (04) IS NOT EQUAL TO  ZEROS
001876                     MOVE  TB-BB-CD-ANUD (04)
001877                                 TO  WS-BB-MENS-CD-OCI-04
001878                 END-IF
001879                 MOVE  WS-BB-MENSAGEM-ERRO     TO  GDA-DESCRICAO-1
001880                 MOVE  SQLCODE   TO  WS-BB-SQLCODE-RESP
001881                 MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
001882             END-IF
001883             MOVE ZEROS TO IND-ERRO
002040             PERFORM 9000-10-RETORNO
002050         END-IF
           END-IF.

002080     ADD  1                      TO  WS-BB-REG-LIDOS.
      *
002091     IF 166-CD-ANUD   EQUAL 100  OR                                 VRS006
002092        166-CD-ANUD   EQUAL 125  OR                                 VRS006
002093        166-CD-ANUD   EQUAL 150  OR                                 VRS006
002094        166-CD-ANUD   EQUAL 175                                     VRS006
      *                                                                   VRS071
002096        IF 166-DT-FIM-CD-ANUD  EQUAL '01.01.0001'
002097           IF 166-IN-DSC-ANUD  EQUAL  '1'
002098              MOVE 166-VL-DSC-ANUD TO WS-BB-VL-DSC-ANUD
002099           END-IF
002100           SET  WIN-OCI  UP  BY  1
002101           IF WIN-OCI LESS 5
002102              MOVE  166-CD-ANUD   TO  TB-BB-CD-ANUD (WIN-OCI)
002103              GO TO  1000-LEITURA-TABELA-AGRUP
002104           ELSE
002105              MOVE WS-BB-TAB-ANUIDADE    TO LK-BB-TAB-ANUIDADE
002106              MOVE WS-BB-QT-AA-VLD-ANUD  TO LK-BB-QT-AA-VLD-ANUD
002107              MOVE WS-BB-QT-AA-CARE-ANUD TO LK-BB-QT-AA-CARE-ANUD
002108              MOVE TB-BB-CD-ANUD (01)    TO LK-BB-CODIGO-OCI
002109              MOVE '0010'                TO GDA-LOCAL
002110              MOVE 1                     TO IND-ERRO
002111              MOVE 'VIPP078A'            TO GDA-PROG-ERRO
002112              MOVE TB-BB-CD-ANUD (01)    TO WS-BB-MENS-CD-OCI-01
002113              MOVE TB-BB-CD-ANUD (02)    TO WS-BB-MENS-CD-OCI-02
002114              MOVE TB-BB-CD-ANUD (03)    TO WS-BB-MENS-CD-OCI-03
002115              MOVE TB-BB-CD-ANUD (04)    TO WS-BB-MENS-CD-OCI-04
002116              MOVE WS-BB-MENSAGEM-ERRO   TO GDA-DESCRICAO-1
002117              MOVE SQLCODE               TO WS-BB-SQLCODE-RESP
002118              MOVE WS-BB-SQLCODE-RESP-R  TO GDA-081-SQLCODE
002119              PERFORM 9000-10-RETORNO
002120           END-IF
002121         ELSE
002122           GO TO  1000-LEITURA-TABELA-AGRUP
002123         END-IF
           END-IF.

002150 2000-LEITURA-TABELA-ANUIDADE.
002160*-----------------------------

002180     MOVE  166-CD-ANUD           TO  140-CD-ANUD.

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
002206            INTO  :140-IN-CBR-PRO-RATD
002207               ,  :140-IN-CBR-APVC-DEB
002208               ,  :140-DT-INC-VGC
002209               ,  :140-DT-FIM-VGC
002210               ,  :140-VL-PCL-TIT
002211               ,  :140-VL-PCL-ADC
002212               ,  :140-QT-PCL-TIT
002213               ,  :140-QT-PCL-ADC
002214               ,  :140-TX-ANUD
002215               ,  :140-CD-MDU-LGC:WS-BB-NOT-NULL-CD-MDU
002216               ,  :140-NR-PRIO-ANUD:WS-BB-NOT-NULL-NR-PRIO
002217               ,  :140-QT-AA-VLD-ANUD:WS-BB-NOT-NULL-VLD-AN
002218               ,  :140-QT-AA-CARE-ANUD:WS-BB-NOT-NULL-CAR-AN
002219               ,  :140-CD-NVL-ACSS:WS-BB-NOT-NULL-NVL-ACSS
                  FROM  DB2VIP.ANUD
002221           WHERE  CD_ANUD  =  :140-CD-ANUD
           END-EXEC.

           IF  WS-BB-NOT-NULL-CD-MDU   IS LESS THAN  ZEROS
002510         MOVE  ZEROS             TO  140-CD-MDU-LGC
           END-IF.

           IF  WS-BB-NOT-NULL-NR-PRIO  IS LESS THAN  ZEROS
002550         MOVE  ZEROS             TO  140-NR-PRIO-ANUD
           END-IF.

           IF  WS-BB-NOT-NULL-VLD-AN   IS LESS THAN  ZEROS
002590         MOVE  ZEROS             TO  140-QT-AA-VLD-ANUD
           END-IF.

           IF  WS-BB-NOT-NULL-CAR-AN   IS LESS THAN  ZEROS
002630         MOVE  ZEROS             TO  140-QT-AA-CARE-ANUD
           END-IF.

           IF  WS-BB-NOT-NULL-NVL-ACSS IS LESS THAN  ZEROS
002634         MOVE  ZEROS             TO  140-CD-NVL-ACSS
           END-IF.

002660     IF  SQLCODE  IS NOT EQUAL TO  ZEROS
002670         IF  SQLCODE  IS NOT EQUAL TO  +100
002680             MOVE  1             TO  IND-ERRO
002690             MOVE  '0091'        TO  GDA-LOCAL
002700             MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
002710             MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
002720             MOVE  'PROBLEMAS NO SELECT TAB. ANUD'
002730                                 TO  GDA-DESCRICAO-1
002740             PERFORM 9000-10-RETORNO
002750         ELSE
002751             IF  140-CD-ANUD  GREATER  99  AND
002752                 140-CD-ANUD   LESS   200
002753                 NEXT SENTENCE
002754             ELSE
002755                 MOVE  1             TO  IND-ERRO
002756                 MOVE  '0006'        TO  GDA-LOCAL
002757                 MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
002758                 MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
002759                 MOVE  'CODIGO DE ANUIDADE INEXISTENTE'
002760                                     TO  GDA-DESCRICAO-1
002761                 PERFORM 9000-10-RETORNO
002762             END-IF
               END-IF
           END-IF.


002860     IF  140-NR-PRIO-ANUD  NOT LESS THAN  WS-BB-NR-PRIO-ANUD
002870         MOVE  140-NR-PRIO-ANUD    TO  WS-BB-NR-PRIO-ANUD
002880         MOVE  140-REG-GERL        TO  WS-BB-TAB-ANUIDADE
002890         MOVE  166-QT-AA-VLD-ANUD  TO  WS-BB-QT-AA-VLD-ANUD
002900         MOVE  166-QT-AA-CARE-ANUD TO  WS-BB-QT-AA-CARE-ANUD
002901         MOVE  166-CD-ANUD         TO  WS-BB-CD-ANUD
           END-IF.

      *    FILTRA-GRUPO-158  (VRS003)
           IF LK-BB-IN-GR-158 = 'S'
              MOVE WS-BB-TAB-ANUIDADE TO LK-BB-TAB-ANUIDADE
           ELSE
002930        GO TO  1000-LEITURA-TABELA-AGRUP
           END-IF.

002950 8000-PESQUISA-CONTA-PARAM.
002960*--------------------------

002980     MOVE  LK-BB-NR-CT-CRT       TO  101-NR-CT-CRT.

           EXEC  SQL
002992           SELECT  CD_MDLD_CRT
002993             INTO  :101-CD-MDLD-CRT
002994             FROM  DB2VIP.CT_CRT
002995            WHERE  NR_CT_CRT = :101-NR-CT-CRT
           END-EXEC.

003060     IF  SQLCODE  IS NOT EQUAL TO  ZEROS
003070         IF  SQLCODE  IS NOT EQUAL TO  +100
003080             MOVE  1             TO  IND-ERRO
003090             MOVE  '0092'        TO  GDA-LOCAL
003100             MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
003110             MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
003120             MOVE  'PROBLEMAS NO SELECT TAB. CT_CRT'
003130                                 TO  GDA-DESCRICAO-1
003140             PERFORM 9000-10-RETORNO
003150         ELSE
003160             MOVE  1             TO  IND-ERRO
003161             MOVE  '0007'        TO  GDA-LOCAL
003180             MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
003190             MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
003200             MOVE  'CONTA INEXISTENTE TAB. CT_CRT'
003210                                 TO  GDA-DESCRICAO-1
003220             PERFORM 9000-10-RETORNO
003230         END-IF
           END-IF.
      *
      *
      * VERIFICA SE A MODALIDE E A SUB ESTá NO GRUPO 109,
      * CASO ESTEJA VERIFICAR QUAL É A ANUDIADE PADRAO PARA ESSA
      * ANUIDADE
      *
      *
           MOVE 'N' TO IND-DSC-SUB

           IF LK-BB-CD-SUB-MDLD-CRT > 0
              INITIALIZE PARM-VIPST752
              MOVE 4                     TO KT752-CD-FUC
              MOVE 101-CD-MDLD-CRT       TO KT752-CD-MDLD-CRT-CRD
              MOVE LK-BB-CD-SUB-MDLD-CRT TO KT752-CD-SUB-MDLD-CRT
              MOVE 107                   TO KT752-CD-GR-SUB-MDLD

              MOVE LENGTH OF PARM-VIPST752 TO EIBCALEN
              CALL  VIPST752 USING DFHEIBLK PARM-VIPST752

              IF KT752-CD-ERRO NOT = ZEROS
                 MOVE 'N'                      TO IND-DSC-SUB
              ELSE
                 MOVE KT752-IND-ANUD           TO IND-DSC-SUB
              END-IF
           END-IF

           IF IND-DSC-SUB = 'S'
              MOVE  101-CD-MDLD-CRT       TO  748-CD-MDLD-CRT-CRD
              MOVE  LK-BB-CD-SUB-MDLD-CRT TO  748-CD-SUB-MDLD-CRT
              MOVE  'ANUIDADE'            TO  748-CD-PRM

              EXEC  SQL
                    SELECT  NR_CTU_PRM
                      INTO  :GDA-ANUD-PADRAO
                      FROM  DB2VIP.PRM_SUB_MDLD
                     WHERE  CD_MDLD_CRT_CRD = :748-CD-MDLD-CRT-CRD
                       AND  CD_SUB_MDLD_CRT = :748-CD-SUB-MDLD-CRT
                       AND  CD_PRM          = :748-CD-PRM
              END-EXEC


              IF  SQLCODE  IS NOT EQUAL TO  ZEROS
                  IF  SQLCODE  IS NOT EQUAL TO  +100
                      MOVE  1             TO  IND-ERRO
                      MOVE  '0093'        TO  GDA-LOCAL
                      MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
                      MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
                      STRING 'PROBLEMAS NO SELECT TAB. '
                             'PRM_SUB_MDLD    '
                      DELIMITED BY SIZE INTO GDA-DESCRICAO-1
                      PERFORM 9000-10-RETORNO
                  ELSE
                      MOVE  1             TO  IND-ERRO
                      MOVE  '0008'        TO  GDA-LOCAL
                      MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
                      MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
                      STRING 'MODALIDADE INEXISTENTE TAB. '
                             'PRM_SUB_MDLD    '
                      DELIMITED BY SIZE INTO GDA-DESCRICAO-1
                      PERFORM 9000-10-RETORNO
                  END-IF
              END-IF
           ELSE
              MOVE  101-CD-MDLD-CRT       TO  164-CD-MDLD-CRT-CRD
              MOVE  'VIP'                 TO  164-SG-SIS
              MOVE  'ANUIDADE'            TO  164-NM-PRM

              EXEC  SQL
                    SELECT  VL_TIP_NUM
                      INTO  :GDA-ANUD-PADRAO
                      FROM  DB2VIP.PRM_MDLD_CRT_CRD
                     WHERE  CD_MDLD_CRT_CRD = :164-CD-MDLD-CRT-CRD
                       AND  SG_SIS          = :164-SG-SIS
                       AND  NM_PRM          = :164-NM-PRM
              END-EXEC

              IF  SQLCODE  IS NOT EQUAL TO  ZEROS
                  IF  SQLCODE  IS NOT EQUAL TO  +100
                      MOVE  1             TO  IND-ERRO
                      MOVE  '0093'        TO  GDA-LOCAL
                      MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
                      MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
                      STRING 'PROBLEMAS NO SELECT TAB. '
                             'PRM_MDLD_CRT_CRD'
                      DELIMITED BY SIZE INTO GDA-DESCRICAO-1
                      PERFORM 9000-10-RETORNO
                  ELSE
                      MOVE  1             TO  IND-ERRO
                      MOVE  '0008'        TO  GDA-LOCAL
                      MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
                      MOVE  WS-BB-SQLCODE-RESP-R TO GDA-081-SQLCODE
                      STRING 'MODALIDADE INEXISTENTE TAB. '
                             'PRM_MDLD_CRT_CRD'
                      DELIMITED BY SIZE INTO GDA-DESCRICAO-1
                      PERFORM 9000-10-RETORNO
                  END-IF
              END-IF
           END-IF

003553     MOVE  GDA-ANUD-PADRAO       TO  166-CD-ANUD
003554                                     WS-BB-ANUD-PDRAO-MDLD.

003590     MOVE  '*'                   TO  WS-BB-FLAG-FINALIZACAO.

003610 8000-99-EXIT.
           EXIT.

003640 9000-10-RETORNO.
003650*----------------

003670     IF  WS-BB-FLAG-LEITURA  EQUAL TO  '*'
003671         EXEC  SQL
003672               CLOSE  CRSPORT
003673         END-EXEC
003690         IF  SQLCODE  NOT EQUAL  ZEROS
003691             MOVE  '0009'        TO  GDA-LOCAL
003692             MOVE  1             TO  IND-ERRO
003693             MOVE  'VIPP078A'    TO  GDA-PROG-ERRO
003730             MOVE  'CLOSE DB2VIP.PORT_ANUD CURSOR CRSPORT'
003740                                 TO  GDA-DESCRICAO-1
003750             MOVE  SQLCODE       TO  WS-BB-SQLCODE-RESP
003760             MOVE  WS-BB-SQLCODE-RESP-R  TO  GDA-081-SQLCODE
003770         END-IF
           END-IF.

003800     GOBACK.