import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import warnings
import io
from io import BytesIO

# Suppress specific warnings from openpyxl
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Function to process the data
@st.cache_data
def load_and_process_data():
    columns_to_string = {
        'Customer[Customer Code]': str,
        'Customer Lifecycle History[Customer Type Descr]': str,
        'Customer Lifecycle History[Customer Type Group]': str,
        'Shop[Shop Code - Descr]': str,
        'Shop[Area Manager]': str,
        'Medical Channel[Mediatype Group Descr]': str,
        'Shop[Area Code]': str,
        'Service Appointment[Service Category Descr]': str,
    }
    df = pd.read_excel('mbreport_query_new.xlsx', dtype=columns_to_string)
    df.columns = [col if not col.startswith('[') else col.strip('[]') for col in df.columns]
    df.rename(columns={'Calendar[ISO Week]': 'ISO Week'}, inplace=True)

    # Calculate the start date by subtracting 12 weeks from now
    now = datetime.now()
    start_date = now - pd.DateOffset(weeks=12)
    start_date = start_date - timedelta(days=start_date.weekday())
    end_date = now + timedelta(days=6 - now.weekday())
    df = df[(df['Calendar[Date]'] >= start_date) & (df['Calendar[Date]'] <= end_date)]
    
    # Add a column mapping Area Code 304 and 109 as specified
    area_mapping = {
        '304': 'A17 TAMARA FUENTE',
        '109': 'A07 ELEONORA ARMONICI',
        '209': 'A21 JESUS TENA',
        '402': 'A34 LORENA EXPOSITO'
    }
    df['Areas'] = df['Shop[Area Code]'].map(area_mapping).fillna('Other Areas')

    # Calculate the number of unique area codes in "Other Areas"
    unique_other_areas = df[df['Areas'] == 'Other Areas']['Shop[Area Code]'].nunique() - len([304, 109, 209, 402])

    df.fillna(0, inplace=True)
    df['Agenda Appointments'] = df.apply(lambda row: row['Agenda_Appointments__Heads_'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['Agenda_Appointments__Heads_'], axis=1)
    df['Opportunity Test'] = df.apply(lambda row: row['Opportunity_Test__Heads_'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['Opportunity_Test__Heads_'], axis=1)
    df['Appointments Completed'] = df.apply(lambda row: row['Appointments_Completed'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['Appointments_Completed'], axis=1)
    df['Appointments Cancelled'] = df.apply(lambda row: row['Appointments_Cancelled'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['Appointments_Cancelled'], axis=1)
    df['Net Trial Activated'] = df.apply(lambda row: row['Net_Trial_Activated__Heads_'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['Net_Trial_Activated__Heads_'], axis=1)
    df['Appointments Rescheduled'] = df.apply(lambda row: row['FP_Appointments_Rescheduled'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['FP_Appointments_Rescheduled'], axis=1)
    df['All Appointments'] = df.apply(lambda row: row['FP_ALL_Appointments'] / unique_other_areas if row['Areas'] == 'Other Areas' else row['FP_ALL_Appointments'], axis=1)
    df['Total_Appointments'] = df['Agenda_Appointments__Heads_'] + df['Appointments_Cancelled']
    df['Total Appointments'] = df.apply(lambda row: ((row['Agenda_Appointments__Heads_'] + row['Appointments_Cancelled']) / unique_other_areas if (row['Agenda_Appointments__Heads_'] + row['Appointments_Cancelled']) != 0 else 0) if row['Areas'] == 'Other Areas' else row['Agenda_Appointments__Heads_'] + row['Appointments_Cancelled'], axis=1)
    df['Appointment to test: Conversion rate'] = np.where(df['Agenda Appointments'] != 0, df['Opportunity Test'] / df['Agenda Appointments'], 0)
    df['Appointment to trial: Conversion rate'] = np.where(df['Agenda Appointments'] != 0, df['Net Trial Activated'] / df['Agenda Appointments'], 0)    
    df['Cancellation rate'] = df['Appointments Cancelled'] / (df['Appointments Cancelled'] + df['Agenda Appointments'])
    df['Reschedule rate'] = df['Appointments Rescheduled'] / df['All Appointments']
    df['Show rate'] = df['Appointments Completed'] / df['Agenda Appointments']
    df['Appointment to trial: Conversion rate'] = np.where(df['Agenda Appointments'] != 0, df['Net Trial Activated'] / df['Agenda Appointments'], 0)    

    return df

# Function to create the overview table
def create_overview_table(df, selected_weeks):
    filtered_df = df[df['ISO Week'].isin(selected_weeks)]
    
    summary = filtered_df.groupby('Areas').agg({
        'All Appointments': 'sum',
        'Total Appointments': 'sum',
        'Appointments Cancelled': 'sum',
        'Appointments Rescheduled': 'sum',
        'Agenda Appointments': 'sum',
        'Appointments Completed': 'sum',
        'Opportunity Test': 'sum',
        'Net Trial Activated': 'sum'
    }).reset_index()

    summary['Appointment to test: Conversion rate'] = (summary['Opportunity Test'] / summary['Agenda Appointments']).apply(lambda x: f"{x:.1%}")
    summary['Appointment to trial: Conversion rate'] = (summary['Net Trial Activated'] / summary['Agenda Appointments']).apply(lambda x: f"{x:.1%}")
    summary['Cancellation rate'] = (summary['Appointments Cancelled'] / (summary['Appointments Cancelled'] + summary['Agenda Appointments'])).apply(lambda x: f"{x:.1%}")
    summary['Reschedule rate'] = (summary['Appointments Rescheduled'] / summary['All Appointments']).apply(lambda x: f"{x:.1%}")
    summary['Show rate'] = (summary['Appointments Completed'] / summary['Agenda Appointments']).apply(lambda x: f"{x:.1%}")

    summary = summary.round(0)
    st.dataframe(summary)

# Function to create visualizations for the overview tab
def create_overview_visualizations(df, selected_weeks):
    filtered_df = df[df['ISO Week'].isin(selected_weeks)]

    st.subheader("Overview Chart")
    summary = filtered_df.groupby('Areas').agg({
        'All Appointments': 'sum',
        'Total Appointments': 'sum',
        'Appointments Cancelled': 'sum',
        'Appointments Rescheduled': 'sum',
        'Agenda Appointments': 'sum',
        'Appointments Completed': 'sum',
        'Opportunity Test': 'sum',
        'Net Trial Activated': 'sum'
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['All Appointments'], name='Sum of All Appointments', text=summary['All Appointments'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Total Appointments'], name='Sum of Total Appointments', text=summary['Total Appointments'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Appointments Cancelled'], name='Sum of Appointments Cancelled', marker_color='red', text=summary['Appointments Cancelled'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Appointments Rescheduled'], name='Sum of Appointments Rescheduled', text=summary['Appointments Rescheduled'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Agenda Appointments'], name='Sum of Agenda Appointments', text=summary['Agenda Appointments'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Appointments Completed'], name='Sum of Appointments Completed', text=summary['Appointments Completed'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Opportunity Test'], name='Sum of Opportunity Test', text=summary['Opportunity Test'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
    fig.add_trace(go.Bar(x=summary['Areas'], y=summary['Net Trial Activated'], name='Sum of Net Trial Activated', text=summary['Net Trial Activated'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))

    fig.update_layout(barmode='group', xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Conversion Rates")
    conversion_data = filtered_df.groupby('Areas').agg({
        'Agenda Appointments': 'sum',
        'Opportunity Test': 'sum',
        'Net Trial Activated': 'sum'
    }).reset_index()
    conversion_data['Appointment to test'] = (conversion_data['Opportunity Test'] / conversion_data['Agenda Appointments']).apply(lambda x: f"{x:.1%}")
    conversion_data['Appointment to trial'] = (conversion_data['Net Trial Activated'] / conversion_data['Agenda Appointments']).apply(lambda x: f"{x:.1%}")
    conversion_data_melted = conversion_data.melt(id_vars=['Areas'], value_vars=['Appointment to test', 'Appointment to trial'], var_name='Conversion Type', value_name='Rate')

    fig = px.bar(conversion_data_melted, x='Areas', y='Rate', color='Conversion Type', barmode='group', title='Conversion Rates by Area', text='Rate')
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', yaxis_ticksuffix = '%')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Cancellation, Reschedule, and Show Rates")
    cancellation_data = filtered_df.groupby('Areas').agg({
        'Appointments Cancelled': 'sum',
        'Appointments Rescheduled': 'sum',
        'Appointments Completed': 'sum',
        'All Appointments': 'sum',
        'Agenda Appointments': 'sum'
    }).reset_index()
    cancellation_data['Cancellation rate'] = (cancellation_data['Appointments Cancelled'] / (cancellation_data['Appointments Cancelled'] + cancellation_data['Agenda Appointments'])).apply(lambda x: f"{x:.1%}")
    cancellation_data['Reschedule rate'] = (cancellation_data['Appointments Rescheduled'] / cancellation_data['All Appointments']).apply(lambda x: f"{x:.1%}")
    cancellation_data['Show rate'] = (cancellation_data['Appointments Completed'] / cancellation_data['Agenda Appointments']).apply(lambda x: f"{x:.1%}")
    cancellation_data_melted = cancellation_data.melt(id_vars=['Areas'], value_vars=['Cancellation rate', 'Reschedule rate', 'Show rate'], var_name='Rate Type', value_name='Rate')

    fig = px.bar(cancellation_data_melted, x='Areas', y='Rate', color='Rate Type', barmode='group', title='Cancellation, Reschedule, and Show Rates by Area', text='Rate')
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', yaxis_ticksuffix = '%')
    st.plotly_chart(fig, use_container_width=True)

# Function to create visualizations for the timeseries tab
def create_timeseries_visualizations(df, selected_metric):
    st.subheader("Time Series Data")
 
    # Define metrics that are rates
    rate_metrics = [
        'Appointment to test: Conversion rate',
        'Appointment to trial: Conversion rate',
        'Cancellation rate',
        'Reschedule rate',
        'Show rate'
    ]
    # Group the data by ISO Week and Areas and aggregate
    timeseries_data = df.groupby(['ISO Week', 'Areas']).agg({
        'All Appointments': 'sum',
        'Total Appointments': 'sum',
        'Appointments Cancelled': 'sum',
        'Appointments Rescheduled': 'sum',
        'Agenda Appointments': 'sum',
        'Appointments Completed': 'sum',
        'Opportunity Test': 'sum',
        'Net Trial Activated': 'sum',
        'Appointment to test: Conversion rate': 'mean',
        'Appointment to trial: Conversion rate': 'mean',
        'Cancellation rate': 'mean',
        'Reschedule rate': 'mean',
        'Show rate': 'mean'
    }).reset_index()
 
    fig = go.Figure()
    for area in timeseries_data['Areas'].unique():
        area_data = timeseries_data[timeseries_data['Areas'] == area]
        y_values = area_data[selected_metric] * 100 if selected_metric in rate_metrics else area_data[selected_metric]
        fig.add_trace(go.Scatter(
            x=area_data['ISO Week'],
            y=y_values,
            mode='lines+markers',
            name=f"{selected_metric} - {area}",
            text=area_data[selected_metric].apply(lambda x: f"{x:,.0f}" if selected_metric not in rate_metrics else f"{x:.1%}"),
            textposition='bottom center',
            hovertemplate=f'{selected_metric}: %{{y:,.0f}}<extra></extra>'
        ))
 
    # Set the y-axis tick suffix based on the metric type
    yaxis_suffix = "%" if selected_metric in rate_metrics else ""
    fig.update_layout(
        title='Time Series of Selected Metric by Area',
        xaxis_title='ISO Week',
        yaxis_title='Value',
        yaxis_ticksuffix=yaxis_suffix,
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)


# Function to create shop details pivot table
def create_shop_details_pivot(df, selected_weeks, selected_area_managers):
    st.subheader("Shop Details")
    if not selected_weeks or not selected_area_managers:
        st.write("Not enough filters to show data.")
    else:
        filtered_df = df[(df['ISO Week'].isin(selected_weeks)) & 
                         (df['Shop[Area Manager]'].isin(selected_area_managers))]
        df_pivot = filtered_df.pivot_table(index=['Shop[Shop Code - Descr]', 'Shop[Area Manager]'],
                                           values=['FP_ALL_Appointments', 'Total_Appointments', 'Agenda_Appointments__Heads_', 'Appointments_Cancelled',
                                                   'FP_Appointments_Rescheduled', 'Appointments_Completed', 'Opportunity_Test__Heads_', 'Net_Trial_Activated__Heads_'],
                                           aggfunc='sum').reset_index()
        df_pivot['Appointment to test: Conversion rate'] = (df_pivot['Opportunity_Test__Heads_'] / df_pivot['Agenda_Appointments__Heads_']).apply(lambda x: f"{x:.2%}")
        df_pivot['Appointment to trial: Conversion rate'] = (df_pivot['Net_Trial_Activated__Heads_'] / df_pivot['Agenda_Appointments__Heads_']).apply(lambda x: f"{x:.2%}")
        df_pivot['Cancellation rate'] = (df_pivot['Appointments_Cancelled'] / (df_pivot['Appointments_Cancelled'] + df_pivot['Agenda_Appointments__Heads_'])).apply(lambda x: f"{x:.2%}")
        df_pivot['Reschedule rate'] = (df_pivot['FP_Appointments_Rescheduled'] / df_pivot['FP_ALL_Appointments']).apply(lambda x: f"{x:.2%}")
        df_pivot['Show rate'] = (df_pivot['Appointments_Completed'] / df_pivot['Agenda_Appointments__Heads_']).apply(lambda x: f"{x:.2%}")
        st.dataframe(df_pivot)

        def to_excel(df):
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            writer.close()  # Use close() instead of save()
            processed_data = output.getvalue()
            return processed_data

        df_xlsx = to_excel(df_pivot)
        st.download_button(label='Download data as Excel', data=df_xlsx, file_name='shop_details.xlsx')


# Streamlit app layout
st.set_page_config(layout="wide")
st.title("MB Report Analysis")

# Load and process data
df = load_and_process_data()
st.write("Data Loaded Successfully")

# Tabs
tab1, tab2, tab3 = st.tabs(["Overview", "Time Series", "Shop Details"])

with tab1:
    if st.button('Update Data'):
        df = load_and_process_data()
        st.write("Data Updated Successfully")

    # Sort ISO weeks for display
    df['ISO Week'] = df['ISO Week'].astype(int)  # Ensure ISO Week is numeric for sorting
    iso_weeks = sorted(df['ISO Week'].unique())  # Sort ISO weeks
   # Ensure months are sorted chronologically and add an "All" option
    months = df['Calendar[Date]'].dt.month_name().unique()
    month_order = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    months_sorted = ["All"] + sorted(months, key=lambda x: month_order.index(x))
    
    # Month multi-selection with "All" option
    selected_months = st.multiselect('Select Month(s)', months_sorted, default=["All"], key='overview_month')
    
    # Check if "All" is selected
    if "All" in selected_months:
        filtered_iso_weeks = iso_weeks  # Show all ISO weeks if "All" is selected
    else:
        # Filter ISO weeks for the selected months only
        filtered_iso_weeks = df[df['Calendar[Date]'].dt.month_name().isin(selected_months)]['ISO Week'].unique()
        filtered_iso_weeks = sorted(filtered_iso_weeks)
    
    # Add "All" option for ISO weeks
    iso_weeks_with_all = ["All"] + filtered_iso_weeks
    
    # ISO week multi-selection with "All" option
    selected_weeks = st.multiselect('Select ISO Weeks', options=iso_weeks_with_all, default="All", key='overview_iso_weeks')
 
    # Check if "All" is selected for ISO weeks
    if "All" in selected_weeks:
        selected_weeks = filtered_iso_weeks  # Include all filtered weeks if "All" is selected
        
    create_overview_table(df, selected_weeks)
    create_overview_visualizations(df, selected_weeks)


with tab2:
    metrics = ['All Appointments', 'Total Appointments', 'Appointments Cancelled', 'Appointments Rescheduled', 'Agenda Appointments', 'Appointments Completed', 'Opportunity Test', 'Net Trial Activated', 'Appointment to test: Conversion rate', 'Appointment to trial: Conversion rate', 'Cancellation rate', 'Reschedule rate', 'Show rate']
    selected_metric = st.selectbox('Select Metric to Display', metrics, index=0, key='timeseries_metric')
    
    create_timeseries_visualizations(df, selected_metric)

with tab3:
    iso_weeks = sorted(df['ISO Week'].unique())  # Sort ISO weeks
    selected_weeks = st.multiselect('Select ISO Weeks', iso_weeks, default=[iso_weeks[-2]], key='shop_iso_weeks')
    area_managers = df['Shop[Area Manager]'].unique()
    default_area_managers = ['Tamara Fuente', 'Eleonora Armonici', 'Lorena Exposito', 'Jesus Tena']
    selected_area_managers = st.multiselect('Select Area Managers', area_managers, default=default_area_managers, key='area_managers')
    
    create_shop_details_pivot(df, selected_weeks, selected_area_managers)
