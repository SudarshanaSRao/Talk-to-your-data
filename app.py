import os
import streamlit as st
import pandas as pd
import pdfplumber
import docx
from PyPDF2 import PdfReader
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
            df = pd.read_csv(file, encoding = 'utf-8') if file_type == "text/csv" else pd.read_excel(file)
            return df
        
        elif file_extension == '.txt':
            return file.getvalue().decode('utf-8')  # Ensure text is decoded as UTF-8
        
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
            return file.getvalue().decode('utf-8')  # Default decoding as UTF-8
    
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# Streamlit UI
st.set_page_config(page_title = "🗣️Data Visualization Assistant", layout = "wide")
st.title("🗣️Data Visualization Assistant")
st.write("Talk to your data -- Upload any file and ask questions about its content!")

# Sidebar for API Key Input
with st.sidebar:
    st.header("🔐 API Configuration")
    api_key = st.text_input(
        "Enter your Anthropic's API Key",
        type = "password",
        placeholder = "sk-...",
    )
    if not api_key:
        st.warning("Please enter your Anthropic's API secret key to proceed.")
    st.markdown("---")
    st.info(
        "You can obtain your API secret key from [Anthropic](https://console.anthropic.com/)."
    )

# File upload widget with spinner
uploaded_file = st.file_uploader("📂 Upload a file", type = None)

if uploaded_file:
    with st.spinner("Processing file..."):
        if not api_key:
            st.error("Please enter your Anthropic API key in the sidebar to proceed.")
        
        else:
            st.session_state['file_content'] = read_file(uploaded_file)
            file_content = st.session_state['file_content']

            if file_content is not None:
                st.subheader("📄 File contents preview")
                
                if isinstance(file_content, pd.DataFrame):
                    st.dataframe(file_content)
                else:
                    # Ensure proper UTF-8 encoding while displaying text
                    try:
                        st.text(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)
                    except UnicodeEncodeError:
                        st.text(file_content.encode('utf-8', 'replace').decode('utf-8')[:1000] + "..." if len(file_content) > 1000 else file_content.encode('utf-8', 'replace').decode('utf-8'))

                st.markdown("---")
                st.subheader("💡 Suggested Questions")

                # Hardcoded suggested questions
                hardcoded_questions = [
                    "What is the main topic of this document?",
                    "Can you summarize the key points?",
                    "Are there any important dates or numbers mentioned?",
                    "What are the main entities or people discussed?",
                    "Can you extract any relevant statistics or data?",
                    "Can you generate a graph showing the correlation between columns?"
                ]

                # Generate additional questions using Claude
                generated_questions = []
                try:
                    client = anthropic.Anthropic(api_key=api_key)

                    system_message = {
                        "type": "text",
                        "text": (
                            "Based on the file content provided, generate 5 thoughtful and contextually relevant questions "
                            "that the user might ask about this document. Focus on key topics, data, or any insights the document could provide."
                        )
                    }

                    response = client.beta.prompt_caching.messages.create(
                        model = "claude-3-5-sonnet-20240620",
                        max_tokens = 2048,
                        system = [system_message],
                        messages = [
                            {
                                "type": "text",
                                "text": f"Here is the content preview:\n\n{str(file_content)[:1000]}..."
                            }
                        ]
                    )

                    if response and "content" in response and response.content:
                        # Parse generated questions from the AI's response
                        ai_response = response.content[0].text.strip()
                        generated_questions = [q.strip() for q in ai_response.split("\n") if q.strip() and not q.startswith("-")]

                except Exception:
                    generated_questions = ["Unable to generate AI-based questions at this time. Please try again later."]

                # Combine hardcoded and generated questions
                all_suggested_questions = hardcoded_questions + generated_questions
                selected_question = st.selectbox(
                    "Choose a question or type your own in the second (below) dialogue box:",
                    [""] + all_suggested_questions
                )

                # User text input for custom questions
                user_question = st.text_input("Ask a question about your file:", value = selected_question)

                # Button to submit the question
                if st.button("Submit"):
                    if user_question:
                        with st.spinner("Generating response..."):
                            try:
                                # Prepare conversation context for Claude
                                system_messages = [
                                    {
                                        "type": "text",
                                        "text": (
                                            "Assume you are a proficient Data Scientist specializing in analyzing various types of documents, "
                                            "extracting insights, and visualizing the data. The user has uploaded a file, and your task is to help "
                                            "them comprehend and analyze its content, offering detailed insights, trends, and visual representations "
                                            "where relevant."
                                        )
                                    },
                                    {
                                        "type": "text",
                                        "text": f"Here is a preview of the file content:\n\n{str(file_content)[:1000]}...",
                                        "cache_control": {"type": "ephemeral"}
                                    }
                                ]

                                if isinstance(file_content, pd.DataFrame):
                                    system_messages.append({
                                        "type": "text",
                                        "text": (
                                            f"This is a tabular dataset with the following properties:\n"
                                            f"Columns: {', '.join(file_content.columns)}\n"
                                            f"Shape: {file_content.shape}\n\n"
                                            f"Basic statistics:\n{file_content.describe().to_string()}"
                                        ),
                                        "cache_control": {"type": "ephemeral"}
                                    })

                                st.session_state['messages'].append({"role": "user", "content": user_question})

                                response = client.beta.prompt_caching.messages.create(
                                    model = "claude-3-5-sonnet-20240620",
                                    max_tokens = 2048,
                                    system = system_messages,
                                    messages = st.session_state['messages']
                                )

                                if response.content:
                                    ai_response = response.content[0].text.strip()
                                    st.session_state['messages'].append({"role": "assistant", "content": ai_response})
                                    st.write("**AI Response:**")
                                    st.write(ai_response)

                                    # Check if AI response suggests creating a visualization
                                    if "generate" in user_question.lower() or "plot" in user_question.lower():
                                        # Example: Generate correlation heatmap if requested
                                        if "correlation" in user_question.lower():
                                            fig, ax = plt.subplots()
                                            sns.heatmap(file_content.corr(), annot = True, cmap = "coolwarm", ax = ax)
                                            st.pyplot(fig)

                                        # Example: Generate bar plot
                                        if "bar" in user_question.lower() or "histogram" in user_question.lower():
                                            fig, ax = plt.subplots()
                                            file_content.plot(kind = 'bar', ax = ax)
                                            st.pyplot(fig)

                                        # Example: Generate scatter plot
                                        if "scatter" in user_question.lower():
                                            fig, ax = plt.subplots()
                                            sns.scatterplot(data = file_content, ax = ax)
                                            st.pyplot(fig)

                                else:
                                    st.write("**AI:** No response received.")

                            except anthropic.APIError as e:
                                st.error("API error: Unable to process the request at the moment.")
                            except Exception:
                                st.error("An unexpected error occurred while processing your question.")

            else:
                st.error("The file could not be read. Please try a different file format.")
else:
    st.info("Please upload a file to begin.")

# Clear conversation history
if st.button("🧹 Clear conversation"):
    if st.session_state['messages']:
        st.session_state['messages'].clear()
        st.session_state['file_content'] = None
        st.success("Conversation history cleared.")
    else:
        st.warning("There are no conversations started to clear.")

# Display conversation history
if st.session_state['messages']:
    st.markdown("---")
    st.subheader("🗨️ Conversation History")
    for msg in st.session_state['messages']:
        if msg['role'] == 'user':
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**AI:** {msg['content']}")
