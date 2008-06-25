#!/usr/bin/python
#     encoding: UTF8

# Fichero de parser de MTD y carga de tablas para PyDBa
import pg             # depends - python-pygresql
import _mysql     # depends - python-mysqldb
import traceback

from pydba_utils import *

class MTDParser_data:
    name=""
    alias=""
    null=False
    dtype="integer"
    length=0
    pk=False
    has_relations_1m=False
    has_relations_m1=False
    

class MTDParser:
    typetr={
        'string'    : 'character varying',
        'double'    : 'double precision',
        'number'    : 'integer',
        'int'       : 'integer',
        'uint'      : 'integer',
        'unit'      : 'smallint',
        'stringlist': 'text',
        'pixmap'    : 'text',
        'unlock'    : 'boolean',
        'serial'    : 'serial',
        'bool'      : 'bool',
        'date'      : 'date',
        'time'      : 'time',
    }
    
    field={}
    primary_key=[]
    def check_field_attrs(self,field,table):
        tfield=MTDParser_data()
        name=getattr(field,"name","noname")
        if not hasattr(field,"name"):
            field.name='no_name'
            print "ERROR: Field name ommitted in MTD %s.%s" % (table,name)
            
        if not hasattr(field,"alias"):
            field.alias=str(field.name)
            print "ERROR: Field alias ommitted in MTD %s.%s" % (table,name)
            
        if not hasattr(field,"type_"):
            field.type_='uint'
            print "ERROR: Field type ommitted in MTD %s.%s" % (table,name)
            
        if not hasattr(field,"length"):
            field.length='0'
            if str(field.type_)=='string':
                field.length='32'
                if hasattr(field,"optionslist"):
                    options=str(field.optionslist).split(";")
                    maxlen=1
                    for option in options:
                        if len(option)>maxlen:
                            maxlen=len(option)
                    
                    field.length=str(maxlen+8)
                else:
                    print "ERROR: Field length ommitted and %s.%s is string." % (table,name)
                
        if not hasattr(field,"pk"):
            field.pk='false'
            print "ERROR: Field pk ommitted in MTD %s.%s" % (table,name)
        
        if not hasattr(field,"null"):
            field.null='true'  # AbanQ permite omitir NULL.
           
        if hasattr(field,"relation"):
            for relation in field.relation:
                relation_is_ok=True
                if not hasattr(relation,"table"):
                    print "ERROR: Relation table ommited in Field %s.%s." % (table,name)
                    relation_is_ok=False
                if not hasattr(relation,"field"):
                    print "ERROR: Relation field ommited in Field %s.%s." % (table,name)
                    relation_is_ok=False
                if not hasattr(relation,"card"):
                    print "ERROR: Relation card ommited in Field %s.%s." % (table,name)
                    relation_is_ok=False
                if relation_is_ok:
                    if str(relation.card)=="1M":
                        tfield.has_relations_1m=True
                    elif str(relation.card)=="M1":
                        tfield.has_relations_m1=True
                    else:
                        print "ERROR: Relation card unknown '%s' in Field %s.%s." % (str(relation.card),table,name)
                                        
        tfield.name=str(field.name)
        tfield.alias=str(field.alias)
        
        if not self.typetr.has_key(str(field.type_)):
            print "ERROR: Unknown field type '%s' in Field %s.%s." % (str(field.type_),table,name)
        else:
            tfield.dtype=self.typetr[str(field.type_)]

        if str(field.pk)=='false':
            tfield.pk=False
        elif str(field.pk)=='true':
            tfield.pk=True
            self.primary_key+=[tfield.name]
        else:
            print "ERROR: Unknown pk '%s' in Field %s.%s." % (str(field.pk),table,name)
        
        if tfield.dtype=='character varying':
            tfield.length=int(str(field.length))
            if (tfield.length<=0):
                print "ERROR: Invalid length '%s' in Field %s.%s." % (str(field.length),table,name)
                
                
            
            
        
        return tfield
        
    
    def parse_mtd(self,mtd):
        self.field={}
        self.primary_key=[]        
        for field in mtd.field:
            tfield=self.check_field_attrs(field,mtd.name)
            self.field[tfield.name]=tfield
            
        

# Crea una tabla según las especificaciones del MTD
def create_table(db,table,mtd,existent_fields=[]):
    existent_fields=set(existent_fields)
    txtfields=[]
    typetr={
        'string'    : 'character varying',
        'double'    : 'double precision',
        'number'    : 'integer',
        'int'       : 'integer',
        'uint'      : 'integer',
        'unit'      : 'smallint',
        'stringlist': 'text',
        'pixmap'    : 'text',
        'unlock'    : 'boolean',
    }
    constraints=[]
    indexes=[]
    if len(existent_fields)>0:
        mode="alter"
    else:
        mode="create"
        
    for field in mtd.field:
        if not str(field.name) in existent_fields:
            row={}
            row['name']=str(field.name)
            if hasattr(field,"type_"):
                row['type']=str(getattr(field,"type_"))
            else:
                print("ERROR: No se encontró tipo de datos para "
                        "%s.%s - se asume int." % (table,str(field.name)))
                row['type']="int"
                
            if typetr.has_key(row['type']):
                row['type']=typetr[row['type']]
                
            if hasattr(field,"length") and row['type']=='character varying':
                length=int(str(field.length))
                if length==0:
                    print "ERROR: Se encontró una longitud 0 para una columna string %s.%s" % (table, str(field.name))
                    length=32
                row['type']+="(%d)" % length
            row['options']=""
            
            if hasattr(field,"null"):
                if str(field.null)=='false' and not hasattr(field,"calculated"):        
                    row['options']+=" NOT NULL"
                    
                if str(field.null)=='true':        
                    if row['type']=='serial':
                        print "ERROR: Se encontró columna %s serial con NULL. Se omite." % str(field.name)
                    else:
                        row['options']+=" NULL"
            else:
                if row['type']=='serial':
                    print "ERROR: Se encontró columna %s serial con NULL. Se omite." % str(field.name)
                else:
                    row['options']+=" NULL"
                            
            if row['type']=='character varying':
                index_adds="text_pattern_ops"
            else:                    
                index_adds=""
            
            if hasattr(field,"pk"):
                if str(field.pk)=='true':
                    if mode=="create":
                        
                        indexes+=["CREATE INDEX %s_%s_m1_idx" 
                                " ON %s USING btree (%s %s);" 
                                % (table,row['name'],table,row['name'],index_adds)]
                        indexes+=["CREATE INDEX %s_%sup_m1_idx" 
                                " ON %s USING btree (upper(%s::text) %s);" 
                                    % (table,row['name'],table,row['name'],index_adds)]
                        constraints+=["CONSTRAINT %s_pkey PRIMARY KEY (%s)" % (table,row['name'])]
                    else:
                        print("ERROR: Cannot alter table to add '%s' as a primary key!."
                                    " Delete table '%s' and try again." % (row['name'],table))
            index_loaded=False
            if hasattr(field,"relation"):
                for relation in field.relation:
                    if hasattr(relation,"card"):
                        if str(relation.card)=='M1' and index_loaded==False:
                            index_loaded=True
                            indexes+=["CREATE INDEX %s_%s_m1_idx" 
                                    " ON %s USING btree (%s %s);" 
                                    % (table,row['name'],table,row['name'],index_adds)]
                            indexes+=["CREATE INDEX %s_%sup_m1_idx" 
                                    " ON %s USING btree (upper(%s::text) %s);" 
                                        % (table,row['name'],table,row['name'],index_adds)]
                    else:
                        print("WARNING: %s.%s has one relation without "
                                "'card' tag" % (table,row['name']))
                
            txtfields+=["\"%(name)s\" %(type)s %(options)s" % row]
    
    if mode=="create":
        txtfields+=constraints
        txtcreate="CREATE TABLE %s (%s) WITHOUT OIDS;" % (table, ",\n".join(txtfields))
        
        
        try:
            db.query(txtcreate)
        except:
            print txtcreate
            raise            
        
        for index in indexes:
            try:
                split_index=index.split(" ")
                index_name=split_index[2]
                # Borrar primero el índice si existe
                qry_indexes = db.query("""
        SELECT pc2.relname as indice
        FROM pg_class pc2 
        WHERE pc2.relname = '%s'
                """ % index_name)
                dt_indexes=qry_indexes.dictresult() 
                for fila in dt_indexes:
                    db.query("DROP INDEX %s;" % fila['indice'])
                
                db.query(index)
            except:
                print index
                import sys
                traceback.print_exc(file=sys.stdout)
    
                
        
        
        
        
def load_mtd(options,db,table,mtd_parse):
    
    mtd=mtd_parse.root.tmd
    if table!=table.lower():
        print "WARNING: Table name '%s' has uppercaps" % table
        table=table.lower()
    if str(mtd.name)!=table:
        print "WARNING: Expected '%s' in MTD name but found '%s' ***" % (table,str(mtd.name))
    
    qry_columns=db.query("SELECT * from information_schema.columns"
                " WHERE table_schema = 'public' AND table_name='%s'" % table)
    #aux_columns
    tablefields={}
    aux_columns=qry_columns.dictresult()
    for column in aux_columns:
        tablefields[column['column_name']]=column
    
    mparser=MTDParser()
    mparser.parse_mtd(mtd)
        
    if len(tablefields)==0:
        if (options.debug):
            print "Creando tabla '%s' ..." % table
        create_table(db,table,mtd)
    else:
        Regenerar=options.rebuildtables
        
        for field in mtd.field:
            name=str(field.name)
            if not tablefields.has_key(name):
                print "ERROR: La columna '%s' no existe en la tabla '%s'" % (name,table)
                Regenerar=True
            #print "*****"
            #for atr in dir(field):
            #    if (atr[0]!='_'):
            #        prin create_table(db,table,mtd)t "%s : '%s'" % (atr,getattr(field,atr))
            
        
        if Regenerar:
            # Borrar primero los índices (todos) que tiene la tabla:
            qry_indexes = db.query("""
    SELECT pc.relname as tabla , pc2.relname as indice,pi.indkey as vector_campos
    FROM pg_class pc 
    INNER JOIN pg_index pi ON pc.oid=pi.indrelid 
    INNER JOIN pg_class pc2 ON pi.indexrelid=pc2.oid
    WHERE NOT pi.indisprimary AND NOT pi.indisunique
    AND pc.relname = '%s'
            """ % table)
            dt_indexes=qry_indexes.dictresult() 
            for fila in dt_indexes:
                db.query("DROP INDEX %s;" % fila['indice'])
            
            data=export_table(options,db,table)
            db.query("DROP TABLE %s" % table)
            create_table(db,table,mtd)
            import_table(options,db,table,data,mparser.field)
            
        try:
            for pkey in mparser.primary_key:
                tfield=mparser.field[pkey]
                if tfield.dtype=='serial':
                    qry_serial=db.query("SELECT pg_get_serial_sequence('%s', '%s') as serial" % (table, tfield.name))
                    dr_serial=qry_serial.dictresult()
                    for dserial in dr_serial:
                        serial=dserial['serial']
                        if serial:
                            qry_maxserial=db.query("SELECT MAX(%s) as max FROM %s" % (tfield.name,table))
                            max_serial=1
                            dr_maxserial=qry_maxserial.dictresult()
                            for dmaxserial in dr_maxserial:
                                if dmaxserial['max']:
                                    max_serial=dmaxserial['max']+1
        
                            db.query("ALTER SEQUENCE %s RESTART WITH %d;" % (serial, max_serial))
        except:
            print "PKeys: %s" % mparser.primary_key
            raise
                
        
        
# Comprobar Primary Keys en una tabla:
# SELECT * FROM information_schema.constraint_table_usage WHERE table_name='articulos'
# SELECT * FROM information_schema.key_column_usage
#

# Obtener el nombre del sequence para una columna y tabla dada:
# SELECT pg_get_serial_sequence('lineasalbaranescli', 'idlinea')

# Obtener los índices
# SELECT pc.relname as tabla , pc2.relname as indice,pi.indkey as vector_campos
#    FROM pg_class pc 
#    INNER JOIN pg_index pi ON pc.oid=pi.indrelid 
#    INNER JOIN pg_class pc2 ON pi.indexrelid=pc2.oid
#  WHERE NOT pi.indisprimary AND NOT pi.indisunique
#
# SELECT pg_get_indexdef(indexrelid) FROM pg_catalog.pg_index WHERE indrelid = 'clientes'::regclass;
# 

# REINICIAR LOS CONTADORES!!!

# ALTER SEQUENCE tallasset_id_seq
#   RESTART WITH 8;
        

def export_table(options,db,table):

    qry = db.query("SELECT * FROM %s" % table)
    filas = qry.dictresult() 
    
    return filas


    
    
    
def import_table(options,db,table,data,nfields):  
    if not len(data):
        return 
    
    if len(data)>1000:
        print "Insertando %d filas en %s ... " % (len(data), table)
    sqlarray=[]
    error=False
    
    for fila in data:
        fields=[]
        values=[]
        copy_values=[]
        sqlvar={}
        for key in fila:
            if nfields.has_key(key):
                campo=fila[key]
                fields+=[key]
                copy_values.append(copy_escapechars(campo))
                if (campo is not None):#Si el valor es nulo
                    values.append("'" + pg.escape_string(str(campo)) + "'")
                else:
                    values.append("NULL")
            
        sqlvar['tabla']=table
        sqlvar['fields']=", ".join(fields)
        sqlvar['values']=", ".join(values)
        sqlarray+=["\t".join(copy_values)]
        
        if len(sqlarray)>2048:
            sql_text="COPY %(tabla)s (%(fields)s) FROM stdin;" % sqlvar
            db.query(sql_text )
            for line in sqlarray:
                db.putline(line+"\n")
            db.putline("\\."+"\n")
            db.endcopy()
            sqlarray=[]
            

    sql_text="COPY %(tabla)s (%(fields)s) FROM stdin;" % sqlvar
    db.query(sql_text )
    for line in sqlarray:
        db.putline(line+"\n")
    db.putline("\\."+"\n")
    db.endcopy()
    sqlarray=[]
    
    if len(data)>1000:
        print "* hecho"
