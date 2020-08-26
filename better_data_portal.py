import pandas as pd
import streamlit as st
from sodapy import Socrata
import base64
import os

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
            st.table(results_table)
            unique, kf = remove_duplicates(kf)
            filename = str(dataset).replace('/', '_') + '.csv'
            link = get_table_download_link(kf, filename)
            msg = f"{unique} unique records. {link}"
            hits[dataset] = {
                "unique": unique,
                "link": link,
                "description": describe_set(resource_ids.get(dataset))
            }
            kf
            st.markdown(msg, unsafe_allow_html=True)

    current_search.markdown('Search complete.')
    bar.markdown(' --- ')
    lines = ""

    for dataset in hits:
        lines += f"  {dataset}: {hits[dataset]['unique']} unique results ({hits[dataset]['link']})  \n"

    final_results.markdown(lines, unsafe_allow_html=True)


def initialize_socrata(data_portal_url, app_token = None):
    client = Socrata(data_portal_url, app_token)
    ds = client.datasets()
    return client, ds


def is_map(resource):
    return 1 if resource['type'] == 'map' else 0


def get_sets(ds):
    resource_ids = {d['resource']['name']: d['resource']['id'] for d in ds if is_map(d['resource']) == 0}
    resource_ids = {k: resource_ids[k] for k in sorted(resource_ids)}
    sets = {d['resource']['id']: d['resource'] for d in ds}
    return resource_ids, sets


def describe_set(id:str) ->dict:
    set = {
        "Name": sets[id]['name'],
        "Resource_id": id,
        "Last Updated": sets[id]['updatedAt'],
        "Description": sets[id]['description'],
        "Columns": list(zip(sets[id]['columns_field_name'], sets[id]['columns_datatype']))
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


@st.cache
def group_sets(datasets: dict):
    groups = {}
    for d in datasets:
        group = d.split(' - ')[0]
        if group in groups:
            groups[group][d] = datasets[d]
        else:
            groups[group] = {d: datasets[d]}

    combined = {}
    # Single sets should not be nested
    for g in groups:
        if len(groups[g]) > 1:
            combined[g] = groups[g]
        if len(groups[g]) == 1:
            combined.update(groups[g])

    sorted_sets = {k: combined[k] for k in sorted(combined)}
    return sorted_sets

try:
    app_token = os.environ['S3_SECRET']
except Exception:
    app_token = None

st.title('Better Data Portal')
st.write('Keyword search across data sets for Socrata data portals')
top_box = st.empty()

about = st.sidebar.button('ABOUT THIS PORTAL')
f = open("about.md", "r")
about_text = f.read()
if about:
    top_box.markdown(about_text)

data_portal_url = st.sidebar.text_input("Data Portal URL", value='data.cityofchicago.org')

# Split the keywords on line breaks and wrap each line in quotes to treat it as a whole phrase
search_terms = st.sidebar.text_area("List keywords, phrases or addresses - one per line")
keywords = search_terms.split('\n')
keywords = [f'"{k}"' for k in keywords]

client, ds = initialize_socrata(data_portal_url, app_token)
resource_ids, sets = get_sets(ds)
sorted_sets = group_sets(resource_ids)
selected_sets = resource_ids.copy()

start_search = st.sidebar.button('SEARCH')
stop_search = st.sidebar.button('STOP')
search_all = st.sidebar.checkbox('Search all data sets', value=True)
st.sidebar.markdown('*Maps are excluded because they are not keyword searchable.*')

if not search_all:
    selected_sets = {}
    available_sets = {}
    for counter, value in enumerate(sorted_sets):
        label = f"{value} ({len(sorted_sets[value])} sets) " if type(sorted_sets[value]) == dict else value
        available_sets[value] = st.sidebar.checkbox(label, False, counter)

    for a in available_sets:
        if type(sorted_sets[a]) == dict and available_sets[a] is True:
            group = sorted_sets[a]
            selected_sets.update(group)
        else:
            if available_sets[a] is True:
                selected_sets[a] = sorted_sets[a]

    # selected_sets = [a for a in available_sets if available_sets[a] is True]
    st.write("Selected data sets")
    st.write(selected_sets)

hits = {}
current_search = st.empty()

if stop_search:
    st.stop()
    st.write('Search halted.')

if start_search:
    top_box.empty()
    main()
