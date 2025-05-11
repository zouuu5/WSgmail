import re
from collections import Counter

import pandas as pd
import seaborn as sns
import streamlit as st
from collections import Counter
import matplotlib.pyplot as plt
import urlextract
import emoji
from wordcloud import WordCloud
import io  # Add this import for BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from datetime import datetime
import traceback 


def generateDataFrame(file):
    data = file.read().decode("utf-8")
    data = data.replace('\u202f', ' ')
    data = data.replace('\n', ' ')
    dt_format = '\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}\s?(?:AM\s|PM\s|am\s|pm\s)?-\s'
    msgs = re.split(dt_format, data)[1:]
    date_times = re.findall(dt_format, data)
    date = []
    time = []
    for dt in date_times:
        date.append(re.search('\d{1,2}/\d{1,2}/\d{2,4}', dt).group())
        time.append(re.search('\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?', dt).group())
    users = []
    message = []
    for m in msgs:
        s = re.split('([\w\W]+?):\s', m)
        if (len(s) < 3):
            users.append("Notifications")
            message.append(s[0])
        else:
            users.append(s[1])
            message.append(s[2])
    df = pd.DataFrame(list(zip(date, time, users, message)), columns=["Date", "Time(U)", "User", "Message"])
    return df


def getUsers(df):
    users = df['User'].unique().tolist()
    users.sort()
    users.remove('Notifications')
    users.insert(0, 'Everyone')
    return users


def PreProcess(df,dayf):
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=dayf)
    df['Time'] = pd.to_datetime(df['Time(U)']).dt.time
    df['year'] = df['Date'].apply(lambda x: int(str(x)[:4]))
    df['month'] = df['Date'].apply(lambda x: int(str(x)[5:7]))
    df['date'] = df['Date'].apply(lambda x: int(str(x)[8:10]))
    df['day'] = df['Date'].apply(lambda x: x.day_name())
    df['hour'] = df['Time'].apply(lambda x: int(str(x)[:2]))
    df['month_name'] = df['Date'].apply(lambda x: x.month_name())
    return df


def getStats(df):
    media = df[df['Message'] == "<Media omitted> "]
    media_cnt = media.shape[0]
    df.drop(media.index, inplace=True)
    deleted_msgs = df[df['Message'] == "This message was deleted "]
    deleted_msgs_cnt = deleted_msgs.shape[0]
    df.drop(deleted_msgs.index, inplace=True)
    temp = df[df['User'] == 'Notifications']
    df.drop(temp.index, inplace=True)
    print("h4")
    extractor = urlextract.URLExtract()
    print("h3")
    links = []
    for msg in df['Message']:
        x = extractor.find_urls(msg)
        if x:
            links.extend(x)
    links_cnt = len(links)
    word_list = []
    for msg in df['Message']:
        word_list.extend(msg.split())
    word_count = len(word_list)
    msg_count = df.shape[0]
    return df, media_cnt, deleted_msgs_cnt, links_cnt, word_count, msg_count


def getEmoji(df):
    emojis = []
    for message in df['Message']:
        emojis.extend([c for c in message if c in emoji.EMOJI_DATA])
    return pd.DataFrame(Counter(emojis).most_common(len(Counter(emojis))))


def getMonthlyTimeline(df):

    df.columns = df.columns.str.strip()
    df=df.reset_index()
    timeline = df.groupby(['year', 'month']).count()['Message'].reset_index()
    time = []
    for i in range(timeline.shape[0]):
        time.append(str(timeline['month'][i]) + "-" + str(timeline['year'][i]))
    timeline['time'] = time
    return timeline


def MostCommonWords(df):
    f = open('stop_hinglish.txt')
    stop_words = f.read()
    f.close()
    words = []
    for message in df['Message']:
        for word in message.lower().split():
            if word not in stop_words:
                words.append(word)
    return pd.DataFrame(Counter(words).most_common(20))

def dailytimeline(df):
    df['taarek'] = df['Date']
    daily_timeline = df.groupby('taarek').count()['Message'].reset_index()
    fig, ax = plt.subplots()
    #ax.figure(figsize=(100, 80))
    ax.plot(daily_timeline['taarek'], daily_timeline['Message'])
    ax.set_ylabel("Messages Sent")
    st.title('Daily Timeline')
    st.pyplot(fig)

def WeekAct(df):
    x = df['day'].value_counts()
    fig, ax = plt.subplots()
    ax.bar(x.index, x.values)
    ax.set_xlabel("Days")
    ax.set_ylabel("Message Sent")
    plt.xticks(rotation='vertical')
    st.pyplot(fig)

def MonthAct(df):
    x = df['month_name'].value_counts()
    fig, ax = plt.subplots()
    ax.bar(x.index, x.values)
    ax.set_xlabel("Months")
    ax.set_ylabel("Message Sent")
    plt.xticks(rotation='vertical')
    st.pyplot(fig)

def activity_heatmap(df):
    period = []
    for hour in df[['day', 'hour']]['hour']:
        if hour == 23:
            period.append(str(hour) + "-" + str('00'))
        elif hour == 0:
            period.append(str('00') + "-" + str(hour + 1))
        else:
            period.append(str(hour) + "-" + str(hour + 1))

    df['period'] = period
    user_heatmap = df.pivot_table(index='day', columns='period', values='Message', aggfunc='count').fillna(0)
    return user_heatmap

def create_wordcloud(df):

    f = open('stop_hinglish.txt', 'r')
    stop_words = f.read()
    f.close()
    def remove_stop_words(message):
        y = []
        for word in message.lower().split():
            if word not in stop_words:
                y.append(word)
        return " ".join(y)

    wc = WordCloud(width=500,height=500,min_font_size=10,background_color='white')
    df['Message'] = df['Message'].apply(remove_stop_words)
    df_wc = wc.generate(df['Message'].str.cat(sep=" "))
    return df_wc

def generate_pdf_report(df, media_cnt, deleted_msgs_cnt, links_cnt, word_count, msg_count, selected_user, emoji_df=None, common_words=None):
    """Generate a PDF report from the chat analysis data"""
    buffer = io.BytesIO()
    
    # Create the PDF object
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor("#075E54"),
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#128C7E"),
        spaceAfter=8
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Add title
    elements.append(Paragraph(f"WhatsApp Chat Analysis Report - {selected_user}", title_style))
    elements.append(Spacer(1, 12))
    
    # Add date
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", normal_style))
    elements.append(Spacer(1, 12))
    
    # Add chat statistics section
    elements.append(Paragraph("Chat Overview", subtitle_style))
    
    # Create statistics table
    stats_data = [
        ["Metric", "Value"],
        ["Total Messages", str(msg_count)],
        ["Total Words", str(word_count)],
        ["Media Shared", str(media_cnt)],
        ["Links Shared", str(links_cnt)],
        ["Deleted Messages", str(deleted_msgs_cnt)]
    ]
    
    stats_table = Table(stats_data, colWidths=[250, 100])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#128C7E")),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 12))
    
    # Add user activity section if it's for Everyone
    if selected_user == "Everyone":
        elements.append(Paragraph("User Activity", subtitle_style))
        user_counts = df['User'].value_counts()
        user_data = [["User", "Message Count", "Percentage"]]
        
        for user, count in user_counts.items():
            if user != "Notifications":
                percentage = round((count / df.shape[0]) * 100, 2)
                user_data.append([user, str(count), f"{percentage}%"])
        
        user_table = Table(user_data, colWidths=[150, 100, 100])
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#128C7E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(user_table)
        elements.append(Spacer(1, 12))
    
    # Add emoji section
    if emoji_df is not None and not emoji_df.empty:
        elements.append(Paragraph("Top Emojis Used", subtitle_style))
        
        emoji_data = [["Emoji", "Count"]]
        for _, row in emoji_df.iterrows():
            if _ < 10:  # Limit to top 10
                emoji_data.append([row['Emoji'], str(row['Count'])])
        
        emoji_table = Table(emoji_data, colWidths=[150, 100])
        emoji_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#128C7E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(emoji_table)
        elements.append(Spacer(1, 12))
    
    # Add common words section
    if common_words is not None and not common_words.empty:
        elements.append(Paragraph("Most Common Words", subtitle_style))
        
        word_data = [["Word", "Count"]]
        for _, row in common_words.iterrows():
            if _ < 10:  # Limit to top 10
                word_data.append([row['Word'], str(row['Count'])])
        
        word_table = Table(word_data, colWidths=[150, 100])
        word_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#128C7E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(word_table)
        elements.append(Spacer(1, 12))
    
    # Add activity patterns section
    elements.append(Paragraph("Activity Patterns", subtitle_style))
    
    # Day activity
    day_counts = df['day'].value_counts()
    day_data = [["Day", "Message Count"]]
    for day, count in day_counts.items():
        day_data.append([day, str(count)])
    
    day_table = Table(day_data, colWidths=[150, 100])
    day_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#128C7E")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(Paragraph("Messages by Day of Week", normal_style))
    elements.append(day_table)
    elements.append(Spacer(1, 12))
    
    # Month activity
    month_counts = df['month_name'].value_counts()
    month_data = [["Month", "Message Count"]]
    for month, count in month_counts.items():
        month_data.append([month, str(count)])
    
    month_table = Table(month_data, colWidths=[150, 100])
    month_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#128C7E")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(Paragraph("Messages by Month", normal_style))
    elements.append(month_table)
    
    # Build the PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
# Replace the send_email_report function with this improved version:
def send_email_report(recipient_email, pdf_buffer, selected_user, username):
    """Send the generated PDF report via email with better error handling"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email.utils import formatdate
    from email import encoders
    import os
    
    # Debug output - will show in the Streamlit UI
    st.write("Starting email process...")
    
    # Email configuration from environment variables
    sender_email = os.environ.get('EMAIL_USER', 'your-app-email@example.com')
    email_password = os.environ.get('EMAIL_PASSWORD', '')
    
    # Debug: Show what credentials we're using (don't show full password in production)
    st.write(f"Using sender email: {sender_email}")
    st.write(f"Password configured: {'Yes' if email_password else 'No'}")
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = f"WhatsApp Chat Analysis Report for {selected_user}"
    
    # Email body
    body = f"""
    Hello {username},
    
    Attached is your WhatsApp Chat Analysis report for {selected_user}.
    Thank you for using our WhatsApp Chat Analyzer!
    
    Regards,
    WhatsApp Chat Analyzer Team
    """
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach PDF
    st.write("Preparing PDF attachment...")
    pdf_buffer.seek(0)  # Reset buffer position to start
    part = MIMEBase('application', 'pdf')
    part.set_payload(pdf_buffer.read())
    encoders.encode_base64(part)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    part.add_header('Content-Disposition', f'attachment; filename="whatsapp_analysis_{selected_user}_{timestamp}.pdf"')
    msg.attach(part)
    
    # Send email with detailed logging
    try:
        st.write("Connecting to SMTP server...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        
        st.write("Starting TLS...")
        server.starttls()
        
        st.write("Attempting login...")
        server.login(sender_email, email_password)
        
        st.write("Sending message...")
        server.send_message(msg)
        
        st.write("Closing connection...")
        server.quit()
        
        st.write("Email sent successfully!")
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Authentication failed: {str(e)}. Check your email and password."
        st.error(error_msg)
        return False, error_msg
    
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        st.error(error_msg)
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        st.error(error_msg)
        return False, error_msg