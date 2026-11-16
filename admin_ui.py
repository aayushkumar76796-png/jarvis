"""Admin dashboard (RBAC-protected): users & roles, passwords, requests, master memory, analytics, audit log."""
import streamlit as st

from auth_utils import (DEFAULT_ADMIN, ROLES, add_or_update_detailed_user, audit_log, change_password, delete_user,
                        get_jarvis_memory, load_users, read_audit_log, save_jarvis_memory, update_user_role, ROLE_PERMISSIONS)
from email_utils import send_reply_email
import email_utils
from history_utils import stats
from request_utils import delete_request, load_requests


def render_admin_dashboard():
    st.subheader("🛠️ Admin Panel & Analytics")
    tabs = st.tabs(["➕ Create User", "👥 Users & Roles", "🔑 Passwords", "📥 Requests", "🧠 Master Memory", "📊 Analytics", "🧾 Audit Log"])

    with tabs[0]:
        with st.form("create_detailed_user"):
            username = st.text_input("Username*")
            password = st.text_input("Password*", type="password")
            role = st.selectbox("Role", ROLES, index=ROLES.index("normal user"))
            name = st.text_input("Full Name")
            school = st.text_input("School Name", value="Aayush Technology High")
            title_pref = st.selectbox("Form of Address", ["Sir", "Username"])
            cls = st.text_input("Class")
            phone = st.text_input("Phone No")
            email = st.text_input("Email")
            if st.form_submit_button("Save & Create User"):
                if username and password:
                    add_or_update_detailed_user(username, password, role, {
                        "name": name, "school": school, "title_pref": title_pref, "class": cls, "phone": phone, "email": email})
                    audit_log("user_created", user=st.session_state.current_user, detail=f"{username} ({role})")
                    st.success(f"User '{username}' created.")
                else:
                    st.error("Username and Password are required.")

    with tabs[1]:
        with st.expander("ℹ️ What each role can do"):
            for r, perms in ROLE_PERMISSIONS.items():
                st.markdown(f"**{r}** → {'everything' if '*' in perms else ', '.join(sorted(perms))}")
        for u_name, u in load_users().items():
            with st.expander(f"👤 {u_name} ({u.get('role', 'normal user')})"):
                with st.form(f"edit_{u_name}"):
                    role = st.selectbox("Role", ROLES, index=ROLES.index(u.get("role", "normal user")), key=f"role_{u_name}")
                    school = st.text_input("School", u.get("school", ""), key=f"school_{u_name}")
                    title = st.selectbox("Title Pref", ["Sir", "Username"], index=0 if u.get("title_pref") == "Sir" else 1, key=f"title_{u_name}")
                    name = st.text_input("Full Name", u.get("name", ""), key=f"name_{u_name}")
                    email = st.text_input("Email", u.get("email", ""), key=f"email_{u_name}")
                    if st.form_submit_button("Update User"):
                        if not update_user_role(u_name, role):
                            st.warning("Role unchanged (cannot demote the last admin).")
                        fresh = load_users()[u_name]
                        add_or_update_detailed_user(u_name, fresh["password"], fresh["role"],
                                                    {"school": school, "title_pref": title, "name": name, "email": email})
                        st.success(f"Updated {u_name}.")
                        st.rerun()
                if u_name != DEFAULT_ADMIN and st.button(f"Delete {u_name}", key=f"del_{u_name}"):
                    if delete_user(u_name):
                        st.success(f"Deleted {u_name}")
                        st.rerun()
                    else:
                        st.error("Cannot delete the last admin.")

    with tabs[2]:
        with st.form("admin_reset_pass"):
            target = st.selectbox("User", list(load_users().keys()))
            p1 = st.text_input("New Password", type="password")
            p2 = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update Password"):
                if p1 and p1 == p2 and len(p1) >= 6:
                    change_password(target, p1)
                    st.success(f"Password for {target} updated (stored hashed).")
                else:
                    st.error("Passwords must match and be at least 6 characters.")

    with tabs[3]:
        reqs = load_requests()
        if not reqs:
            st.info("No pending requests.")
        for idx, r in enumerate(reqs):
            with st.expander(f"Request from {r['name']} ({r['email']})"):
                st.write(f"**Phone:** {r['phone']}  \n**Address/Reason:** {r['address']}  \n**Hobby/Target:** {r['hobby']} / {r['target']}")
                with st.form(f"reply_{idx}"):
                    subj = st.text_input("Subject", "Regarding your Jarvis Access Request")
                    body = st.text_area("Message")
                    if st.form_submit_button("📧 Send Reply"):
                        ok = send_reply_email(r["email"], subj, body)
                        (st.success if ok else st.error)(email_utils.LAST_STATUS)
                if st.button("🗑️ Delete Request", key=f"delreq_{idx}"):
                    delete_request(idx)
                    st.rerun()

    with tabs[4]:
        with st.form("master_memory_form"):
            text = st.text_area("Master Core Memory (jarvis_memory.txt)", get_jarvis_memory(), height=250)
            if st.form_submit_button("💾 Save"):
                save_jarvis_memory(text)
                st.success("Saved.")

    with tabs[5]:
        s = stats()
        a, b, c, d = st.columns(4)
        a.metric("👥 Users", len(load_users()))
        b.metric("📥 Requests", len(load_requests()))
        c.metric("💬 Chat sessions", s["sessions"])
        d.metric("🧾 Messages", s["messages"])
        if s["per_user"]:
            st.markdown("**Sessions per user**")
            st.bar_chart(s["per_user"])

    with tabs[6]:
        log = read_audit_log(150)
        st.dataframe(log, use_container_width=True) if log else st.info("No events yet.")
