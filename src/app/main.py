import base64
import json
import os
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import requests
import requests.auth
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv
import logging
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated, Union



load_dotenv()

app=FastAPI()

logging.basicConfig(level=logging.INFO)


fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

def get_profile(userName: str):
    base_url= os.getenv("TRIRIGA_BASE_API_URL","")
    result=requests.get(f'{base_url}/oslc/spq/cstPeopleLookupQC?oslc.select=*&oslc.where=spi:triUserNameTX="{userName}"', auth=requests.auth.HTTPBasicAuth(os.getenv("username") ,os.getenv("password")))
    profile_payload=json.loads(result.text)
    jsession_id=result.cookies.get_dict()['JSESSIONID']
    return {"profile_payload": profile_payload, "jsession_id": jsession_id}


def get_building_id(id: str,jsession_id: str ):
    base_url= os.getenv("TRIRIGA_BASE_API_URL","")
    result=requests.get(f"{base_url}/oslc/so/triLocationRS/{id}", headers={"Cookie":f"JSESSIONID={jsession_id};"})
    location_payload=remove_namespace(json.loads(result.text))
    building_url=location_payload["triAssociatedBuilding"]["resource"]
    building_id=building_url.split("/")[-1]
    return building_id


class service_request(BaseModel):
    
    # triRequestedForTX: str=Field('')
    # triRequestedByTX: str=Field('')
    triDescriptionTX: str
    triCustomerOrgTX: str = Field("\\Organizations\\DEFAULT Workgroup (for Default Service Plans)")
    action: str= Field('Create Draft')
    triOperationTX:str= Field("Create")
    triBuildingTX:str= Field("Test Building")
    triRequestForLI:str= Field("Someone Else")
    triRequestClassCL:str= Field("Lights Out")
    triRequestClassRecordIDTX:str= Field("2270583")
    triUserNameTX:str
    triServiceRequestFormTX: str=Field("Electrical & Lighting")

    # class Config:
    #     fields = {
    #         "triUserNameTX": {"exclude": True}
    #     }





def remove_namespace(data):
    new_dict = {}
    for key, value in data.items(): #items return list of tuples
        if ':' in key:
            new_key = key.split(':')[-1]
        else:
            new_key = key
        new_dict[new_key] = value
        if isinstance(value, dict):
            new_dict[new_key] = remove_namespace(value)

        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            new_list=[]
            for dict_data in value:
                new_list.append(remove_namespace(dict_data))
            new_dict[new_key] = new_list


    return new_dict





@app.get("/")
def test_app(current_user: Annotated [User, Depends(get_current_active_user)]):
    return "App is working fine"



#For future reference

# def add_namespace(data):
#     new_dict = {}
#     namespace=os.getenv("NAMESPACE", "spi")
#     for key, value in data.items(): #items return list of tuples
#         new_key = namespace + ":" + key
#         new_dict[new_key] = value
#         if isinstance(value, dict):
#             new_dict[key] = add_namespace(value)

#         if isinstance(value, list) and isinstance(value[0], dict):
#             new_list=[]
#             for dict_data in value:
#                 new_list.append(add_namespace(dict_data))
#             new_dict[new_key] = new_list

#     return new_dict

# Below operation is to get the service ticket details. For future reference

# @app.get("/get_sr/{sr_id}")
# def get_service_request(sr_id: str):

#     try:
#         base_url= os.getenv("TRIRIGA_BASE_API_URL","")
#         result=requests.get(f"{base_url}/clean115/oslc/so/triAPICOutboundServiceRequestRS/{sr_id}", auth=requests.auth.HTTPBasicAuth(os.getenv("USERNAME"),os.getenv("PASSWORD")))
#         namespaces_removed_data=json.loads(result.text)
#         namespaces_removed_data=remove_namespace(namespaces_removed_data)
#         return {"response": namespaces_removed_data}
#     except Exception as e:
#         print(e.with_traceback)



def add_namespace_on_keys(service_request: dict):
    new_values={}
    namespace=os.getenv("NAMESPACE", "spi")
    for key, value in service_request.items():
        new_key = f'{namespace}:{key}'
        new_values[new_key] = value
    service_request.update(new_values)

    return new_values


def get_ui_id(request_id: str, jsession_id: str):

    try:
        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        result=requests.get(f"{base_url}/oslc/so/triRequestRS/{request_id}", headers={"Cookie":f"JSESSIONID={jsession_id};"})
        result=remove_namespace(json.loads(result.text))
        return {"ui_id": result["triIdTX"]}
    except Exception as e:
        print(e.with_traceback)


def get_location_ref_with_jsession_id(user_name: str):
        
        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        result=requests.get(f'{base_url}/oslc/spq/cstPeopleLookupQC?oslc.select=*&oslc.where=spi:triUserNameTX="{user_name}"', auth=requests.auth.HTTPBasicAuth(os.getenv("username") ,os.getenv("password")))
        jsession_id=result.cookies.get_dict()['JSESSIONID']
        result=remove_namespace(json.loads(result.text))
        location_ref=result["member"][0]["cstAssociatedLocation"]["resource"]
        return {"location_ref":location_ref, "jssession_id": jsession_id}

def get_building_id(location_ref: str, jsession_id: str):
        result=requests.get(location_ref, headers={"Cookie":f"JSESSIONID={jsession_id};"})
        result=remove_namespace(json.loads(result.text))
        building_ref=result["cstAssociatedBuilding"]["resource"]
        building_id=building_ref.split("/")[-1]
        return building_id



@app.get("/get_sr_request_categories/{user_name}")
def get_sr_request_categories(user_name:str, current_user: Annotated [User, Depends(get_current_active_user)]):

    try:
        categories_list=[]
        logging.info("Service request defaults")

        location_ref_with_jsession_id=get_location_ref_with_jsession_id(user_name)

        location_ref=location_ref_with_jsession_id["location_ref"]
        jsession_id=location_ref_with_jsession_id["jssession_id"]


        building_id=get_building_id(location_ref, jsession_id)


        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        result=requests.get(f"{base_url}/oslc/spq/cstLocationsQC?oslc.select=*,spi:cstAssociatedBuildingServices%7B*%7D,spi:cstAssociatedBuildingServiceCategories%7B*%7D&oslc.where=dcterms:identifier={building_id}", auth=requests.auth.HTTPBasicAuth(os.getenv("username") ,os.getenv("password")))
        payload_without_namespaces=remove_namespace(json.loads(result.text))
        categories_payload=payload_without_namespaces["member"][0]["cstAssociatedBuildingServiceCategories"]

        for category_object in categories_payload:
            categories_list.append({"triNameTX" : category_object["triNameTX"], "identifier": category_object["identifier"]})

        return {"building_id": building_id,"categories": categories_list }
    
    except Exception as e:
        print(e.with_traceback)


@app.get("/get_sr_request_services/{user_name}/{building_id}/{category_id}")
def get_sr_request_services_based_on_category(user_name:str, building_id:str, category_id:str, current_user: Annotated [User, Depends(get_current_active_user)]):

    try:
        services_list=[]
        logging.info("Services based on category")

        location_ref_with_jsession_id=get_location_ref_with_jsession_id(user_name)
        jsession_id=location_ref_with_jsession_id["jssession_id"]

        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        result=requests.get(f"{base_url}/api/v1/query/dataByQueryName?moduleName=Location&boName=triBuilding&queryName=triBuilding%20-%20%20OSLC%20-%20Associated%20Building%20Services&filtCount=2&filterValue0={building_id}&filterType0=10&dsId0=0&sectionName0=General&fieldName0=triRecordIdSY&filterValue1={category_id}&filterType1=10&dsId1=1&sectionName1=RecordInformation&fieldName1=triParentIdSY", headers={"Cookie":f"JSESSIONID={jsession_id};"})

        if len(json.loads(result.text)["data"])==0:
            return {"status_code": 404}
        
        payload_without_namespaces=remove_namespace(json.loads(result.text))
        services_payload=payload_without_namespaces["data"]

        for service_object in services_payload:
            services_list.append({"triNameTX" : service_object["1-RecordInformation-triNameTX"], "identifier": service_object["1-RecordInformation-triRecordIdSY"], "category_identifier": service_object["1-RecordInformation-triParentIdSY"]})

        return {"building_id": building_id,"services": services_list }
    
    except Exception as e:
        print(e.with_traceback)





@app.post("/create_sr",     openapi_extra={
        "requestBody": {
            "content": {"application/json": {"schema": service_request.model_json_schema()}},
            "required": True,
        },
    },
)
def create_service_request(service_request : service_request, current_user: Annotated [User, Depends(get_current_active_user)]):

    try:

        logging.info("Created service method starts")
        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        logging.info("Orchestrate payload   " + json.dumps(dict(service_request)))

        
        profile_details_with_jsession=get_profile(service_request.triUserNameTX)
        profile_payload_without_namespaces=remove_namespace(profile_details_with_jsession["profile_payload"])
        jsession_id=profile_details_with_jsession["jsession_id"]


        organization=profile_payload_without_namespaces["member"][0]["triPrimaryOrganization-triPathTX"]
        location=profile_payload_without_namespaces["member"][0]["triSpacePrimaryLocation-triPathTX"]
        identifier=profile_payload_without_namespaces["member"][0]["identifier"]


        result=None

        if organization and location:
            
            building_str_start_index=location.find("\\", 2) + 1
            service_request.triCustomerOrgTX=organization
            service_request.triBuildingTX= location[building_str_start_index: location.find("\\",building_str_start_index)]

            service_request_dict=vars(service_request)
            del service_request_dict['triUserNameTX']
            service_request_dict["triRequestedForTX"]=identifier
            service_request_dict["triRequestedByTX"]=identifier

            request_payload=add_namespace_on_keys(service_request_dict)

            logging.info("TRIRIGA payload   " + json.dumps(request_payload))

            result=requests.post(f"{base_url}/oslc/so/triAPICServiceRequestCF", data=json.dumps(request_payload) , 
                                headers={"Properties":os.getenv("PROPERTIES_HEADER"),
                                        "Content-Type":"application/json",
                                        "Cookie":f"JSESSIONID={jsession_id};"})
            
            
            payload_without_namespaces=remove_namespace(json.loads(result.text))            
            request_id=payload_without_namespaces["triTRIRIGAIDTX"]

        elif service_request.triCustomerOrgTX!="" and service_request.triBuildingTX!="":

            service_request_dict=vars(service_request)
            del service_request_dict['triUserNameTX']

            service_request_dict["triRequestedForTX"]=identifier
            service_request_dict["triRequestedByTX"]=identifier


            request_payload=add_namespace_on_keys(service_request_dict)
            result=requests.post(f"{base_url}/oslc/so/triAPICServiceRequestCF", data=json.dumps(request_payload) ,
                                headers={"Properties":os.getenv("PROPERTIES_HEADER"),
                                        "Content-Type":"application/json",
                                        "Cookie":f"JSESSIONID={jsession_id};"})
            
            payload_without_namespaces=remove_namespace(json.loads(result.text))
            request_id=payload_without_namespaces["triTRIRIGAIDTX"]

        
        elif not organization:
            return "Organization is not associated with the user"
        else:
            return "Building is not associated to user "

        if request_id:

            # logging.info("Created service request with request ID", request_id )
            ui_id_response=get_ui_id(request_id, jsession_id)
            ui_id=ui_id_response["ui_id"]

            # logging.info("UI ID service request", ui_id )
        
        else:

            return "UI ID is not associated with the user"



        # html_content = f"""
        # <a href="{base_url}/WebProcess.srv?objectId=750000&actionId=750011&specId={request_id}">{ui_id}</a>
        #             """

        return {'display_result':f"Service Request: <a href='{base_url}/WebProcess.srv?objectId=750000&actionId=750011&specId={request_id}'>{ui_id}</a>",
                 'ticket_details': payload_without_namespaces }

    except Exception as e:
        print(e.with_traceback)



@app.get("/getMyActiveRequests")
def getMyActiveRequests(current_user: Annotated [User, Depends(get_current_active_user)]):

    try:
        logging.info("Get all active requests")
        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        
        return {'display_result':f"Service Request: <a href='{base_url}/app/tririga/#name=Landing+Page+-+Manage+Requests'>Active Requests</a>"}
    except Exception as e:
        print(e.with_traceback)




@app.get("/get_requestclass")
def get_request_class(current_user: Annotated [User, Depends(get_current_active_user)]):

    try:
        logging.info("Request classes")

        members_values_array=[]
        members_lookup_dict_array={}

        base_url= os.getenv("TRIRIGA_BASE_API_URL","")
        result=requests.get(f"{base_url}/oslc/spq/triRequestClassQC?oslc.select=*", auth=requests.auth.HTTPBasicAuth(os.getenv("username") ,os.getenv("password")))
        payload_without_namespaces=remove_namespace(json.loads(result.text))
        members_array=payload_without_namespaces["member"]

        for member in members_array:
            member_name=member["triNameTX"]
            member_id=member["identifier"]
            members_values_array.append(member_name)
            members_lookup_dict_array.update({f"{member_name}" :  member_id})
        
        members_values_array.sort()

        return {"members": members_values_array , "members_look_up_table": members_lookup_dict_array}
    except Exception as e:
        print(e.with_traceback)



desc = """
A wrapper written using Python FastAPI framework to access the TRIRIGA APIs.
"""


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="FastAPI Wrapper for TRIRIGA API",
        version="1.0.0",
        openapi_version="3.0.0",
        description=desc,
        routes=app.routes,
        
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi