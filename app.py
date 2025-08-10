import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
import re

st.set_page_config(layout="wide", page_title="Underdog Exposures")

st.title("Underdog Player Exposure")

def combine_names(df, col_first, col_last, col_new="Name"):
    '''Create a new "Name" column that holds both the first and last names'''
    df = df.copy()
    df[col_new] = df.apply(lambda row: f"{row[col_first]} {row[col_last]}", axis=1)
    return df

def get_build(df):
    df = df.copy()
    df["team_pick_number"] = ((df['Pick Number'] - 1) // 12) + 1
    df_builds = df.pivot(
        index="Draft", columns="team_pick_number", values="Position"
        ).apply(
            lambda row: row.value_counts(), axis=1
        )
    ser_summary = (
        df_builds["QB"].astype(str) + "-" +
        df_builds["RB"].astype(str) + "-" +
        df_builds["WR"].astype(str) + "-" +
        df_builds["TE"].astype(str)
    )
    return ser_summary.value_counts()

def process_exposures():
    file = st.session_state['uploaded_file']
    if file is not None:
        df_upload = pd.read_csv(file)
        draft_count = len(df_upload["Draft"].unique())
        ser_exp = df_upload.groupby("Appearance")["Draft"].count()
        df_exp = ser_exp.reset_index(drop=False)
        df_exp.columns = ["id", "exp"]
        df_exp["exp"] = (df_exp["exp"]/draft_count).round(3)
        # make percentile
        df_exp["exp"] *= 100
        st.session_state['df_exp'] = df_exp
        st.session_state['build'] = get_build(df_upload)

p = Path("data")

id_dfs = {}
for file in p.iterdir():
    if file.name.startswith("ids-"):
        match = re.match(r"^ids-(.+)\.csv$", file.name)
        if match:
            tourn = match.group(1)
            id_dfs[tourn] = pd.read_csv(file)

contests = sorted(id_dfs.keys())
bbm_index = contests.index("BBM")

st.write("The player ADPs are as of August 9, 2025.")

choice = st.selectbox("Select the BBM or Eliminator (BBM will also work for contests like Puppy)", 
                      contests, index=bbm_index)

df_adp = pd.read_csv(p/f"ids-{choice}.csv")

df_adp = combine_names(df_adp, "firstName", "lastName")
df_adp["adp"] = pd.to_numeric(df_adp["adp"], errors='coerce')

st.file_uploader(
    "Upload your Eliminator Exposure csv file",
    type="csv",
    key='uploaded_file',
    on_change=process_exposures,
    accept_multiple_files=False
)

# Show dataframe if available
if 'df_exp' in st.session_state:
    df_merge = df_adp.merge(st.session_state['df_exp'], on="id", how="left")
    df_reduced = df_merge[["adp", "Name", "exp"]].copy()
    df_reduced = df_reduced.rename({"exp": "Exposure"}, axis=1)

    # If your DataFrame is named df_reduced
    df = df_reduced.reset_index(drop=True)
    if df["Exposure"].isna().sum() == len(df):
        st.markdown("**Warning!** No player matches found, please double check the tournament choice.")

    df["Exposure"] = df["Exposure"].fillna(0)

    # Parameters
    N_COLS = 12

    # Add row and snake_col for boustrophedon (snaking) layout
    df['row'] = df.index // N_COLS
    df['col'] = df.index % N_COLS
    df['snake_col'] = df.apply(
        lambda x: N_COLS - 1 - x['col'] if x['row'] % 2 == 1 else x['col'],
        axis=1
    )

    # Prepare text for display (adp, name, exposure with 1 decimal and %)
    df['label'] = (
        df['adp'].astype(str) + ': ' +
        df['Name'] + '\n' +
        df['Exposure'].round(1).astype(str) + '%'
    )

    df['adp_label'] = df['adp'].astype(str)
    df['name_label'] = df['Name']
    df['exposure_label'] = df['Exposure'].round(1).astype(str) + '%'

    df = df.query("row < 25")

    # Find min/max for color scale
    exposure_min = df['Exposure'].min()
    exposure_max = df['Exposure'].max()
    exposure_mid = 8.3

    # Base rectangle chart
    rects = alt.Chart(df).mark_rect(stroke='black').encode(
        x=alt.X('snake_col:O', title='', axis=None),
        y=alt.Y('row:O', title='', axis=None),
        color=alt.Color(
            'Exposure:Q',
            scale=alt.Scale(
                scheme='redblue',
                domain=[exposure_min, exposure_mid, exposure_max],
                reverse=True
            ),
            legend=alt.Legend(title="Exposure (%)")
        ),
        tooltip=['adp', 'Name', alt.Tooltip('Exposure:Q', format='.1f')]
    )

    texts_adp = alt.Chart(df).mark_text(
        fontSize=12,
        fontWeight='bold',
        dy=-25,  # Shift up
    ).encode(
        x=alt.X('snake_col:O'),
        y=alt.Y('row:O'),
        text=alt.Text('adp_label:N')
    )

    texts_name = alt.Chart(df).mark_text(
        fontSize=12,
        dy=0,  # Centered
    ).encode(
        x=alt.X('snake_col:O'),
        y=alt.Y('row:O'),
        text=alt.Text('name_label:N')
    )

    texts_exposure = alt.Chart(df).mark_text(
        fontSize=12,
        dy=25,  # Shift down
    ).encode(
        x=alt.X('snake_col:O'),
        y=alt.Y('row:O'),
        text=alt.Text('exposure_label:N')
    )

    # Combine and set chart size
    chart = (
        rects +
        texts_adp +
        texts_name +
        texts_exposure
    ).properties(
        width=N_COLS * 200,
        height=(df['row'].max() + 1) * 100,
        title="Players by ADP and Exposure"
    )

    st.altair_chart(chart, use_container_width=True)

    ser_builds = st.session_state['build']

    st.write("Build frequencies:")

    build_string = "  \n".join([f"{count} times: {build}" for build, count in ser_builds.items()])
    st.markdown(build_string)