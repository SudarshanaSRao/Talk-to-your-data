import os
import streamlit as st
import pandas as pd
import pdfplumber
import docx
from PyPDF2 import PdfReader
import json
from io import StringIO
import anthropic
import matplotlib.pyplot as plt
import seaborn as sns

# Initialize session state for conversation
if 'messages' not in st.session_state:
    st.session_state['messages'] = []
if 'file_content' not in st.session_state:
    st.session_state['file_content'] = None

# Function to read different file types
def read_file(file):
    file_type = file.type
    file_extension = os.path.splitext(file.name)[1].lower()

    try:
        if file_type in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            df = pd.read_csv(file) if file_type == "text/csv" else pd.read_excel(file)
            return df.to_string()
        elif file_extension == '.txt':
            return file.getvalue().decode('utf-8')
        elif file_extension == '.pdf':
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        elif file_extension in ['.doc', '.docx']:
            doc = docx.Document(file)
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            return file.getvalue().decode('utf-8')
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# Streamlit UI
st.set_page_config(page_title="File Conversational Assistant", layout="wide")
st.title("📄 File Conversational Assistant")
st.write("Upload any file and ask questions about its content!")

# Sidebar for API Key Input
with st.sidebar:
    st.header("🔐 API Configuration")
    api_key = st.text_input(
        "Enter your Anthropics API Key",
        type="password",
        placeholder="sk-...",
    )
    if not api_key:
        st.warning("Please enter your Anthropics API key to proceed.")
    st.markdown("---")
    st.info(
        "You can obtain your API key from [Anthropic](https://console.anthropic.com/)."
    )

# File upload widget with spinner
uploaded_file = st.file_uploader("📂 Upload a file", type=None)

if uploaded_file:
    with st.spinner("Processing file..."):
        if not api_key:
            st.error("Please enter your Anthropic API key in the sidebar to proceed.")
        else:
            st.session_state['file_content'] = read_file(uploaded_file)
            file_content = st.session_state['file_content']

            if file_content is not None:
                st.subheader("📄 File Content Preview")
                st.text(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)

                st.markdown("---")
                st.subheader("💬 Chat about your file")

                # Text input for user question
                st.markdown("---")
                st.subheader("💡 Suggested Questions")
                suggested_questions = [
                    "What is the main topic of this document?",
                    "Can you summarize the key points?",
                    "Are there any important dates or numbers mentioned?",
                    "What are the main entities or people discussed?",
                    "Can you extract any relevant statistics or data?"
                ]
                selected_question = st.selectbox("Choose a question or type your own:", [""] + suggested_questions)
                user_question = st.text_input("Ask a question about your file:", value=selected_question)

                # Button to submit the question
                if st.button("Submit Question"):
                    if user_question:
                        with st.spinner("Generating response..."):
                            try:
                                client = anthropic.Anthropic(api_key=api_key)

                                # Prepare system messages
                                system_messages = [
                                    {
                                        "type": "text",
                                        "text": "You are an AI assistant specializing in analyzing various types of documents and extracting insights. The user has uploaded a file, and you should help them understand and analyze its content."
                                    },
                                    {
                                        "type": "text",
                                        "text": f"Here is a preview of the file content:\n\n{file_content[:1000]}...",
                                        "cache_control": {"type": "ephemeral"}
                                    }
                                ]

                                if isinstance(file_content, pd.DataFrame):
                                    system_messages.append({
                                        "type": "text",
                                        "text": f"This is a tabular dataset with the following properties:\nColumns: {', '.join(file_content.columns)}\nShape: {file_content.shape}\n\nBasic statistics:\n{file_content.describe().to_string()}",
                                        "cache_control": {"type": "ephemeral"}
                                    })

                                # Append user message
                                st.session_state['messages'].append({"role": "user", "content": user_question})

                                response = client.beta.prompt_caching.messages.create(
                                    model="claude-3-5-sonnet-20240620",
                                    max_tokens=2048,
                                    system=system_messages,
                                    messages=st.session_state['messages']
                                )

                                if response.content:
                                    ai_response = response.content[0].text.strip()
                                    st.session_state['messages'].append({"role": "assistant", "content": ai_response})
                                    st.write("**AI Response:**")
                                    st.write(ai_response)
                                else:
                                    st.write("**AI:** No response received.")
                            except anthropic.APIError as e:
                                st.error(f"An error occurred with the API: {e}")
                            except Exception as e:
                                st.error(f"An unexpected error occurred: {e}")

                if "generate a visualization" in user_question.lower():
                    try:
                        df = pd.read_csv(StringIO(file_content)) if isinstance(file_content, str) else pd.DataFrame(file_content)
                        fig, ax = plt.subplots()
                        sns.heatmap(df.corr(), ax=ax)
                        st.pyplot(fig)
                    except Exception as e:
                        st.error(f"Unable to generate visualization: {e}")

            else:
                st.error("The file could not be read. Please try a different file format.")
else:
    st.info("Please upload a file to begin.")

# Display conversation history
if st.session_state['messages']:
    st.markdown("---")
    st.subheader("🗨️ Conversation History")
    for msg in st.session_state['messages']:
        if msg['role'] == 'user':
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**AI:** {msg['content']}")

# Option to clear conversation
if st.button("🧹 Clear Conversation"):
    st.session_state['messages'] = []
    st.session_state['file_content'] = None
    st.success("Conversation history cleared.")
    st.experimental_rerun()
