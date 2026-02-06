from openai import OpenAI
import tiktoken

key = ""  # input your key
client = OpenAI(api_key=key, base_url="https://us.api.openai.com/v1")
encoding = tiktoken.get_encoding("o200k_base")

token_stats = {
    'total_input_tokens': 0,
    'total_output_tokens': 0
}

def count_tokens(text):
    return len(encoding.encode(text))

def calculate_cost(input_tokens, output_tokens):
    input_cost = (input_tokens / 1_000_000) * 1.250
    output_cost = (output_tokens / 1_000_000) * 10.000
    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost

def analyze_email(email_content):
    system_content = """You are an expert at analyzing phishing emails.

    CRITICAL RULES:
    1. Analyze ONLY the original email.
    2. Base answers ONLY on explicit evidence found in the text. Do NOT infer or guess.
    3. Output MUST be a valid JSON object only. Do NOT use Markdown code blocks (```json). No conversational text.
    4. Generally, select the SINGLE most appropriate option. 
       Exception: For Question 2, select the 'Multiple actions' option ONLY if the email offers distinct ALTERNATIVE methods to execute the scam (e.g., Call OR Click). IGNORE administrative footer links (unsubscribe, privacy policy).
    """

    user_content = f"""Analyze this phishing email and answer two questions:

1. (Type) What type of content does the email contain?
   1) Account Security / Credential Alert
   2) Invoice / Payment
   3) Document Sharing
   4) Shipping / Delivery
   5) Internal Business Request / Boss Fraud
   6) Government related-task
   7) Tech Support / Antivirus
   8) Reward
   9) Promotion / Product Offer
   10) Employment / Job Opportunity
   11) Extortion / Blackmail / Sextortion
   12) Romance / Personal Relationship
   13) Survey / Feedback / Membership
   14) Health / Medical
   15) Business Inquiry
   16) Random string
   17) None

2. (Action) What is the behavioral mechanism or technical action explicitly requested?
   INSTRUCTIONS: Focus on the technical method the user must use to comply with REQUEST.
   - Single Action: Select the matching option.
   - Multiple Actions: Select Option 6 and list the option numbers in 'detail' (e.g., "1, 3").

   1) Navigate to a URL (Click links, Buttons, Scan QR Codes - Includes "View Document" or "Sign Here" links)
   2) Perform Offline Communication (Call a phone number, Send SMS/Text)
   3) Interact with Payload (Download/Open attached files, Install software)
   4) Direct Email Reply (Compose a reply, Send requested info via return email)
   5) Forwarding (Forward this email to others)
   6) Multiple actions (e.g., "Call this number OR Click this link". Specify option numbers in 'detail')
   7) None (Informational only, no action requested)

Return ONLY a JSON object in this exact format:
{{
  "Type": <number>,
  "Action": <number>,
  "detail": "<optional: only if Action is 6>"
}}

Email:
{email_content}
"""
    
    input_tokens = count_tokens(system_content) + count_tokens(user_content)
    token_stats['total_input_tokens'] += input_tokens
        
    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {
                "role": "system", 
                "content": system_content
            },
            {
                "role": "user", 
                "content": user_content
            }
        ]
    )

    response_text = response.choices[0].message.content.strip()
    output_tokens = count_tokens(response_text)
    
    token_stats['total_output_tokens'] += output_tokens
    
    print(f"Input tokens: {input_tokens:,}, Output tokens: {output_tokens:,}")
    print(f"Response: {response_text}")
    
    input_cost, output_cost, total_cost = calculate_cost(input_tokens, output_tokens)
    print(f"Input cost: ${input_cost:.4f}, Output cost: ${output_cost:.4f}, Total cost: ${total_cost:.4f}")
    
    return response_text

if __name__ == "__main__":
    email_content = """
    Subject: Urgent: Your Account Has Been Suspended
    
    Dear Customer,
    
    We have detected unusual activity on your account. Please click the link below 
    to verify your identity within 24 hours, or your account will be permanently closed.
    
    Verify Now: http://fake-banking-site.com/verify
    
    Thank you,
    Security Team
    """ 
    
    result = analyze_email(email_content)
    print(f"\n=== Total Statistics ===")
    print(f"Total input tokens: {token_stats['total_input_tokens']:,}")
    print(f"Total output tokens: {token_stats['total_output_tokens']:,}")
