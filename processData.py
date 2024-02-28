import pandas as pd
import numpy as np
import re
import os


def processMedPrescription(medP):
    medP["ORDER_DATE"]=pd.to_datetime(medP["ORDER_DATE"])
    medP["END_DATE"]=pd.to_datetime(medP["END_DATE"])
    medP["START_DATE"]=pd.to_datetime(medP["START_DATE"])

    # exclude "historical records" (order date later than start date)
    medP=medP[medP["ORDER_DATE"]<=medP["START_DATE"]]

    # exclude possible invalid prescription (start date later than or equal to end date)
    medP=medP[~(medP["START_DATE"]>=medP["END_DATE"])]

    # drop duplicates on ["STUDY_ID",'START_DATE','generic_name']
    medP=medP.drop_duplicates(subset=["STUDY_ID",'START_DATE','MEDICATION_NAME'])

    return medP

def processMedList(med_list, mapping_list):
    def is_float(string):
        ## check whether a word is float number, like "0.9"
        try:
            float(string)
            return True
        except ValueError:
            return False

    def get_strength(string,med):
        ## [string] is the generic name
        ## [med] is the Opioid name
        
        string=string.lower()
        
        ## split generic name to separated words
        l=re.split("[- (),%]",string)

        ## find the index where the OPIOID name appears
        index=l.index(med)
        a=""
        for i in l:
            ## check whether strength is described in some other units, like Example 2
            if "/" in i:
                a=i.split("/")[-1]   # a is unit value
                index_a=l.index(i)
                if a.isdigit() or is_float(a):
                    a+=l[index_a+1]   #a + unit name
                break
        for i in range(index,len(l)):
            ## take the closest digit to OPIOID as strength
            if l[i].isdigit() or is_float(l[i]):
                strength=l[i]
                if l[i+1].isdigit():  # strength like 1,100 would be separated as ["1","100"], merge them together here
                    strength+=l[i+1]
                    i=i+1
                if "/" in l[i+1]:
                    strength+=l[i+1].split("/")[0]    # take the gram amounts with strength if it's like "mg/ml"
                else:
                    strength+=l[i+1]
                break

        if a in strength:
            return strength      # direct gram amounts
        return strength+"/"+a    # gram amounts / units

    med_list=med_list.loc[:,['medication_name', 'simple_generic_title',
       'generic_name', 'strength']]
    med_list=med_list.drop_duplicates().sort_values(['generic_name'])
    
    for row in med_list.itertuples():
        simple_generic_title=row[med_list.columns.to_list().index("simple_generic_title")+1]    
        generic_name=row[med_list.columns.to_list().index("generic_name")+1]           
        l=re.split("[- ()/,.%]",simple_generic_title)    
        name=generic_name              # initiate [name]          
        flag=True
        strength=''
        unit=''
        
        for i in l:
            if i.lower() in mapping_list:
                name=i.lower()    # name is the OPIOID name
                flag=False 
                ## check whether this generic title has mentioned any OPIOID (whether it is an uninterested meds)
                ## flag=False: it is an OPIOID med in our interested list
                break
        med_list.loc[row[0],'med']=name
        
        
        if flag:
            ## drop uninterested meds, and move to next row
            med_list=med_list.drop(row[0])
            continue
        else:
            ## get strength based on generic_name and OPIOID name.
            med_strength=get_strength(generic_name,name)
            
            
        if "/" in med_strength:
            ## example1: med_strength is "1,100 mg/55 ml"
            ## example2: med_strength is '500 mg/ml'
            
            ## assign the columns of "med_strength" and "strength_unit"
            med_list.loc[row[0],'med_strength']=med_strength.split("/")[0]
            med_list.loc[row[0],'strength_unit']=med_strength.split("/")[1]
            
            ## extract digit part 
            for digit1 in med_strength.split("/")[0]:
                if digit1.isdigit() or digit1=='.':
                    strength+=digit1
                else:
                    break
            for digit2 in med_strength.split("/")[1]:
                if digit2.isdigit() or digit2=='.':
                    unit+=digit2
                else:
                    break
            if unit=='':
                unit=1
            
            ## convert to signle unit strength
            ## example1 "1,100 mg/55 ml" (a=1100, b=55) to "20" mg/ml
            ## example2 "500 mg/ml" (a=500, b=1) to "500" mg/ml
            med_list.loc[row[0],'med_strength_byunit']=float(strength)/float(unit)
        
        else:
            ## example "20 mg"
            med_list.loc[row[0],'med_strength']=med_strength
            for digit3 in med_strength:
                if digit3.isdigit() or digit3=='.':
                    strength+=digit3
                else:
                    break
            med_list.loc[row[0],'med_strength_byunit']=float(strength)
        
        ## check whether the strength is in micro- level
        ## convert it to milli- level
        if "mc" in med_strength:
            med_list.loc[row[0],'med_strength_byunit']=med_list.loc[row[0],'med_strength_byunit']/1000
        
        ## for unit as "tablet" and 'capsule', use itself as unit
        unit_list=["tablet",'capsule']
        for i in unit_list:
            if i in generic_name:
                med_list.loc[row[0],'strength_unit']=i
    return med_list

def processData(medP, med_list, mapping_list):
    full_record=pd.merge(medP,med_list, left_on="MEDICATION_NAME", right_on="medication_name", how="inner")
    full_record=full_record.drop_duplicates(subset=['STUDY_ID', 'ORDER_DATE', 'MEDICATION_NAME',
       'DOSE', 'MED_UNIT', 'QUANTITY',
       'REFILLS', 'START_DATE', 'END_DATE', 'FREQUENCY',
       'simple_generic_title', 'generic_name', 'strength',
       'med', 'med_strength', 'strength_unit'])

    full_record=full_record.sort_values(by=["STUDY_ID","START_DATE"])

    full_record=full_record.loc[:,['STUDY_ID', 'ORDER_DATE', 'MED_ORDER_ID', 'MEDICATION_NAME',
        'DOSE', 'MED_UNIT', 'QUANTITY',
        'REFILLS', 'START_DATE', 'END_DATE', 'FREQUENCY',
        'simple_generic_title', 'generic_name', 'strength',
        'med', 'med_strength','med_strength_byunit', 'strength_unit']]
    
    for row in full_record.itertuples():
        quantity=row[full_record.columns.to_list().index("QUANTITY")+1]
        med_strength_byunit=row[full_record.columns.to_list().index("med_strength_byunit")+1]
        med=row[full_record.columns.to_list().index("med")+1]
        if not pd.isna(quantity) and not pd.isna(med_strength_byunit):
            a=float(quantity.split(" ")[0])     ## quantity
            b=med_strength_byunit             ## med_strength_byunit
            full_record.loc[row[0],"med_consumption"]=a*b
            if med!="methadone":
                full_record.loc[row[0],"MME_CF"]=mapping_list[med]
                if row[15]=='fentanyl':
                    #hr=getHrs(row[11])
                    full_record.loc[row[0],"MME_consumption"]=a*72*b*mapping_list[med]
                    ## 72 hrs for all Fentanyl
                else:
                    full_record.loc[row[0],"MME_consumption"]=a*b*mapping_list[med]
            else:
                if a*b/float(30)<=20:
                    full_record.loc[row[0],"MME_CF"]=4
                    full_record.loc[row[0],"MME_consumption"]=a*b*4
                elif a*b/float(30)<=40:
                    full_record.loc[row[0],"MME_CF"]=8
                    full_record.loc[row[0],"MME_consumption"]=a*b*8
                elif a*b/float(30)<=60:
                    full_record.loc[row[0],"MME_CF"]=10
                    full_record.loc[row[0],"MME_consumption"]=a*b*10
                else:
                    full_record.loc[row[0],"MME_CF"]=12
                    full_record.loc[row[0],"MME_consumption"]=a*b*12
    
    return full_record