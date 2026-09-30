import streamlit as st
from assessment import LEVELS, SKILLS, N_ITEMS, generate_item, grade_production
from planner import make_plan
from storage import load, save
from llm import tts, stt, chat

st.set_page_config(page_title="Polski Tutor", page_icon="🇵🇱")
ss = st.session_state
if "profile" not in ss:
    ss.profile = load()
    ss.stage = "learn" if ss.profile.get("plan") else "onboarding"
for k, v in {"skill_i": 0, "q_i": 0, "lvl_i": 1, "item": None, "messages": []}.items():
    ss.setdefault(k, v)

@st.cache_data(show_spinner=False)
def transcribe(b: bytes) -> str:          # avoid re-calling STT on every rerun
    return stt(b)

# ---------- Stage 1: onboarding ----------
def onboarding():
    st.title("🇵🇱 Your Polish Tutor")
    goal = st.text_input("Why are you learning Polish?", "Daily life and work in Kraków")
    minutes = st.slider("Minutes per day", 10, 90, 30, 5)
    if st.button("Start placement test"):
        ss.profile.update(goal=goal, minutes=minutes, levels={}, mistakes=[])
        ss.stage = "placement"; st.rerun()

# ---------- Stage 2: placement ----------
def advance():
    skill = SKILLS[ss.skill_i]
    ss.item, ss.q_i = None, ss.q_i + 1
    if ss.q_i >= N_ITEMS[skill]:
        ss.profile["levels"][skill] = LEVELS[ss.lvl_i]
        ss.skill_i, ss.q_i, ss.lvl_i = ss.skill_i + 1, 0, 1
        if ss.skill_i == len(SKILLS):
            with st.spinner("Building your learning plan..."):
                ss.profile["plan"] = make_plan(ss.profile["levels"],
                                               ss.profile["goal"], ss.profile["minutes"])
            save(ss.profile); ss.stage = "plan"
    st.rerun()

def placement():
    skill = SKILLS[ss.skill_i]
    st.header(f"Placement test – {skill.title()} ({ss.q_i + 1}/{N_ITEMS[skill]})")
    st.progress(ss.skill_i / len(SKILLS))
    if ss.item is None:
        with st.spinner("Preparing question..."):
            ss.item = generate_item(skill, LEVELS[ss.lvl_i])
            if skill == "listening":
                ss.item["audio"] = tts(ss.item["text"])
    item, key = ss.item, f"{skill}_{ss.q_i}"

    if skill in ("reading", "listening"):
        if skill == "reading":
            st.markdown(f"> {item['text']}")
        else:
            st.audio(item["audio"], format="audio/mp3")
        choice = st.radio(item["question"], item["options"], index=None, key=key)
        if st.button("Submit", disabled=choice is None):
            correct = item["options"].index(choice) == item["answer_index"]
            ss.lvl_i = min(ss.lvl_i + 1, 4) if correct else max(ss.lvl_i - 1, 0)
            advance()
    else:
        st.info(item["task"])
        if skill == "writing":
            answer = st.text_area("Your answer in Polish", key=key)
        else:
            audio = st.audio_input("Record your answer", key=key)
            answer = transcribe(audio.getvalue()) if audio else ""
            if answer:
                st.caption(f"Transcript: {answer}")
        if st.button("Submit", disabled=not answer):
            with st.spinner("Grading..."):
                g = grade_production(skill, item["task"], answer)
            ss.lvl_i = LEVELS.index(g["cefr"])
            ss.profile["mistakes"] += g.get("errors", [])
            advance()

# ---------- Stage 3: plan ----------
def plan():
    st.header("Your results")
    st.table({"Skill": list(ss.profile["levels"]), "Level": list(ss.profile["levels"].values())})
    st.subheader("Learning plan")
    st.write(ss.profile["plan"]["summary"])
    for w in ss.profile["plan"]["weeks"]:
        with st.expander(f"Week {w['week']} – {w['focus']}"):
            st.dataframe(w["sessions"], hide_index=True)
    if st.button("Start learning"):
        ss.stage = "learn"; st.rerun()

# ---------- Stage 4: learning ----------
def learn():
    lv = ss.profile["levels"]
    st.sidebar.write({k: v for k, v in lv.items()})
    if st.sidebar.button("View plan"):
        ss.stage = "plan"; st.rerun()
    tab_chat, tab_practice = st.tabs(["💬 Tutor chat", "🎯 Practice"])

    with tab_chat:
        system = (f"You are a patient Polish tutor. Learner levels: {lv}. "
                  f"Goal: {ss.profile['goal']}. Speak Polish at the learner's level, "
                  "correct mistakes gently (show wrong → right + short rule), "
                  f"and revisit these past mistakes: {ss.profile['mistakes'][-10:]}")
        for m in ss.messages:
            st.chat_message(m["role"]).write(m["content"])
        if prompt := st.chat_input("Napisz coś po polsku..."):
            ss.messages.append({"role": "user", "content": prompt})
            reply = chat([{"role": "system", "content": system}] + ss.messages)
            ss.messages.append({"role": "assistant", "content": reply}); st.rerun()

    with tab_practice:
        skill = min(lv, key=lambda s: LEVELS.index(lv[s]))  # weakest skill first
        st.write(f"Today's focus: **{skill}** at **{lv[skill]}**")
        # Reuse generate_item / grade_production exactly as in placement,
        # then append errors to ss.profile["mistakes"] and save(ss.profile).

PAGES = {"onboarding": onboarding, "placement": placement, "plan": plan, "learn": learn}
PAGES[ss.stage]()