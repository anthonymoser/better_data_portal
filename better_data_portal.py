import pandas as pd
import streamlit as st
from sodapy import Socrata
import base64
import os
import requests

def main():

    bar = st.progress(0)
    st.markdown('## RESULTS')
    final_results = st.empty()
    descriptions = {}
    description_buttons = {}

    for counter, dataset in enumerate(selected_sets, 1):
        bar.progress(counter / len(selected_sets))
        # For each data set, get the resource id and reset the dataframe
        resource = selected_sets[dataset]
        kf = None

        current_search.markdown(f'Currently searching: {dataset}')
        results_table = []

        try:
            for k in keywords:
                results = client.get(resource, q=k)
                df = pd.DataFrame.from_records(results)

                # If there's already some data, append new results; otherwise make a dataframe
                if len(results) > 0:
                    if kf is not None:
                        kf = kf.append(df, sort=True)
                    else:
                        kf = df
                    row = {
                        "keyword": k,
                        "results": len(results)
                    }
                    results_table.append(row)

        except Exception as e:
            # msg = f'Error checking dataset: {e}\n'
            # st.write(msg)
            continue

        if kf is not None:
            st.markdown(f'### {dataset}')
            unique, kf = remove_duplicates(kf)
            filename = str(dataset).replace('/', '_') + '.csv'
            link = get_table_download_link(kf, filename)
            msg = f"{unique} unique records. {link} ([Source info](https://{data_portal_url}/d/{resource}))"

            hits[dataset] = {
                "unique": unique,
                "link": link,
                "description": describe_set(resource_ids.get(dataset))
            }
            st.markdown(msg, unsafe_allow_html=True)
            st.table(results_table)
            kf

    current_search.markdown('Search complete.')
    bar.markdown(' --- ')
    lines = ""

    for dataset in hits:
        lines += f"  {dataset}: {hits[dataset]['unique']} unique results ({hits[dataset]['link']})  \n"

    final_results.markdown(lines, unsafe_allow_html=True)

@st.cache_resource
def initialize_socrata(data_portal_url, app_token = None):
    client = Socrata(data_portal_url, app_token)
    return client

@st.cache_data
def get_data_portals()->list:
    st.write('Just copy and paste the URL into the "Data Portal URL" box and start searching. To quickly find a data portal on this page, use Ctrl+F or Command+F.')
    st.write('Data Portal URL : Number of Data Sets')
    response = requests.get('http://api.us.socrata.com/api/catalog/v1/domains')
    results = response.json()['results']
    data_portals = {r['domain']: r['count'] for r in sorted( results, key=lambda item: item['domain']) if r['count'] > 0}
    st.write(f'{len(data_portals)} data portals available.')
    st.dataframe(pd.DataFrame(results).sort_values('count', ascending=False))


def describe_set(id:str) ->dict:
    set = {
        "Name": sets[id]['name'],
        "Resource_id": id,
        "Last Updated": sets[id]['updatedAt'],
        "Description": sets[id]['description'],
        "Columns": dict(zip(sets[id]['columns_field_name'], sets[id]['columns_datatype']))
    }
    return set


def remove_duplicates(kf):
    # Don't include dictionaries while checking for duplicates
    columns = list(kf.columns)
    exclude = []

    for c in columns:
        for d in kf[c].dropna().values.tolist():
            if type(d) == dict:
                exclude.append(c)
                break

    subset = [c for c in columns if c not in exclude]
    kf = kf.drop_duplicates(subset=subset)
    return len(kf), kf


def get_table_download_link(df, download_filename, link_text="CSV"):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    href = f'<a href="data:file/csv;base64,{b64}" download="{download_filename}">{link_text}</a>'
    return href


def get_resources(url, limit, offset):
    response = requests.get(f"http://api.us.socrata.com/api/catalog/v1?domains={url}&only=datasets&derived=false&limit={limit}&offset={offset}")
    return response.json()['results']

@st.cache_data
def get_datasets(data_portal_url):
    datasets = []
    resources = None
    limit = 100
    offset = 0
    page = 1
    while resources is None or len(resources) == limit:
        print(page)
        resources = get_resources(data_portal_url, limit, offset)
        datasets += resources 
        offset += limit
        page += 1 
    return datasets


############## GLOBAL LOGIC #################
try:
    app_token = os.environ['S3_SECRET']
except Exception:
    app_token = None

st.set_page_config(
    layout="wide",  # Can be "centered" or "wide". In the future also "dashboard", etc.
    initial_sidebar_state="expanded",  # Can be "auto", "expanded", "collapsed"
    page_title='Better Data Portal',  # String or None. Strings get appended with "• Streamlit".
    page_icon=None,  # String, anything supported by st.image, or None.
)

st.title('Better Data Portal')
st.write('Keyword search across data sets for Socrata data portals')
top_box = st.empty()

about = st.sidebar.button('ABOUT THIS SITE')
find_portals = st.sidebar.button('FIND OTHER DATA PORTALS')

f = open("about.md", "r")
about_text = f.read()
if about:
    top_box.markdown(about_text)

if find_portals:
    get_data_portals()


url_params = st.experimental_get_query_params()

if 'portal_url' in url_params.keys():
    portal_url = url_params['portal_url'][0]
else:
    portal_url = 'data.cityofchicago.org'
    
data_portal_url = st.sidebar.text_input("Data Portal URL", value=portal_url)

# Split the keywords on line breaks and wrap each line in quotes to treat it as a whole phrase
search_terms = st.sidebar.text_area("List keywords, phrases or addresses - one per line")
keywords = search_terms.split('\n')
keywords = [f'"{k}"' for k in keywords]

start_search = st.sidebar.button('SEARCH')
stop_search = st.sidebar.button('STOP')
search_all = st.sidebar.checkbox('Search all data sets', value=True)

client = initialize_socrata(data_portal_url, app_token)
ds = get_datasets(data_portal_url)
resource_ids = {d['resource']['name']: d['resource']['id'] for d in ds}
selected_sets = resource_ids.copy()

sets = {d['resource']['id']: d['resource'] for d in ds}
set_list = pd.DataFrame([
        {
            'selected': False,
            'name':sets[id]['name'],
            'description': sets[id]['description'],
            'updated_at': sets[id]['updatedAt'],
            'columns_name': sets[id]['columns_name'],
            'id': sets[id]['id'], 
            'link': f"https://{data_portal_url}/d/{id}", 
            'download_dataset': f'https://{data_portal_url}/api/views/{id}/rows.csv?accessType=DOWNLOAD'
        } for id in sets
    ]).sort_values('name')

st.sidebar.markdown('*Some data sets are excluded - click About This Site for more.*')
selections_list = st.sidebar.empty()

if not search_all:
    ds_filter = st.text_input('Enter text to filter the data sets')
    if ds_filter:
        filtered = set_list.pipe(lambda df: df[df.name.str.contains(ds_filter)])
    else:
        filtered = set_list.copy()
    edited_df = st.experimental_data_editor(filtered)
    checked_boxes = list(edited_df.pipe(lambda df: df[df.selected]).name)
    selections_list.table(checked_boxes)
    selected_sets = {set_name:selected_sets[set_name] for set_name in selected_sets if set_name in checked_boxes}

hits = {}
current_search = st.empty()

if stop_search:
    st.stop()
    st.write('Search halted.')

if start_search:
    top_box.empty()
    main()
