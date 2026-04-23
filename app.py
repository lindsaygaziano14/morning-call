import os
import traceback
import anthropic
from flask import Flask, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

current_briefing = {"text": "Good morning. Your briefing is not ready yet."}


def generate_briefing():
    ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = ai.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
       messages=[{
            "role": "user",
            "content": (
                "You are calling Lindsay on the phone at 6am to wake her up. It's morning in Boston. "
                "Search for today's top news headlines and current Boston weather. "
                "Write a spoken morning briefing — about 2 minutes when read aloud. "
                "Tone: peppy, warm, genuinely excited to be talking to her. Think hype coach, not drill sergeant. "
                "Structure in this exact order: "
                "1. Energetic greeting by name and something positive about the day. "
                "2. Three news headlines with brief context, 1-2 sentences each. "
                "3. Boston weather for today. "
                "4. Then say: Alright Lindsay, let's run through Bruce Lee's five affirmations together. Say them with me. "
                "5. Then speak these five affirmations one by one, with a brief pause between each, reading them slowly and with conviction: "
                "I am the best. "
                "I can do it alone. "
                "God is always with me. "
                "I am a winner. "
                "Today is my day. "
                "6. End with one short, punchy send-off to start her day. "
                "Write ONLY the spoken words — no markdown, no bullet points, no stage directions, no numbered lists in the output. "
                "Use natural spoken language throughout."
            )
        }]
    )

    briefing_text = " ".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()

    if not briefing_text:
        briefing_text = "Good morning Lindsay. Something went wrong generating your briefing. But you still need to get up."

    current_briefing["text"] = briefing_text
    return briefing_text


def make_call():
    twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    call = twilio.calls.create(
        to=os.environ["YOUR_PHONE_NUMBER"],
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        url=f"{os.environ['APP_URL']}/twiml",
    )
    return call.sid


@app.route("/twiml", methods=["GET", "POST"])
def twiml():
    response = VoiceResponse()
    response.say(current_briefing["text"], voice="Polly.Matthew-Neural", language="en-US")
    return Response(str(response), mimetype="text/xml")


@app.route("/trigger")
def trigger():
    try:
        briefing = generate_briefing()
        call_sid = make_call()
        return f"<h2>Call triggered!</h2><p>Call SID: {call_sid}</p><h3>Briefing:</h3><p>{briefing}</p>", 200
    except Exception as e:
        tb = traceback.format_exc()
        return f"<h2>Error</h2><pre>{tb}</pre>", 500


@app.route("/health")
def health():
    env_status = {
        key: ("SET" if os.environ.get(key) else "MISSING")
        for key in [
            "ANTHROPIC_API_KEY",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_PHONE_NUMBER",
            "YOUR_PHONE_NUMBER",
            "APP_URL",
        ]
    }
    return env_status, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
