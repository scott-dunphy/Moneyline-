import streamlit as st
import uuid
import os

# Initialize session state
if 'rooms' not in st.session_state:
    st.session_state.rooms = {}

# Initialize user's session
if 'user' not in st.session_state:
    st.session_state.user = {}

def calculate_money_line(yes_votes, no_votes):
    """
    Calculate money line based on votes.
    The money line is calculated as:
    - For "Yes": (Total votes / Yes votes) * 100
    - For "No": (Total votes / No votes) * 100
    """
    total = yes_votes + no_votes
    if total == 0:
        return 0, 0
    yes_ml = (total / yes_votes) * 100 if yes_votes > 0 else 0
    no_ml = (total / no_votes) * 100 if no_votes > 0 else 0
    return yes_ml, no_ml

def main():
    st.title("Live Voting & Money Line Calculator")

    # Create or join a room
    st.header("Create or Join a Room")
    with st.form("join_room"):
        name = st.text_input("Enter your name")
        room_id = st.text_input("Enter room ID (leave blank to create new room)")
        submitted = st.form_submit_button("Join/Create Room")

        if submitted:
            if not room_id:
                # Create new room
                room_id = str(uuid.uuid4())[:6]  # Shorten UUID for simplicity
                if room_id not in st.session_state.rooms:
                    st.session_state.rooms[room_id] = {
                        'users': {},
                        'votes': {'yes': 0, 'no': 0}
                    }
                st.success(f"Created new room: {room_id}")
            else:
                if room_id in st.session_state.rooms:
                    if name not in st.session_state.rooms[room_id]['users']:
                        st.session_state.rooms[room_id]['users'][name] = None
                    st.success(f"Joined room: {room_id}")
                else:
                    st.error("Room does not exist!")

            # Store user's room and name in session
            st.session_state.user['room'] = room_id
            st.session_state.user['name'] = name

    # Only show voting interface if user is in a room
    if 'room' in st.session_state.user:
        room_id = st.session_state.user['room']
        room = st.session_state.rooms.get(room_id, None)

        if room is None:
            st.error("You are not in a valid room!")
        else:
            st.header("Voting Interface")
            st.subheader(f"Room: {room_id}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Vote Yes"):
                    room['votes']['yes'] += 1
                    room['users'][st.session_state.user['name']] = 'yes'
                    st.rerun()

            with col2:
                if st.button("Vote No"):
                    room['votes']['no'] += 1
                    room['users'][st.session_state.user['name']] = 'no'
                    st.rerun()

            # Display current votes
            st.subheader("Current Results")
            yes_votes = room['votes']['yes']
            no_votes = room['votes']['no']
            total_votes = yes_votes + no_votes

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Yes Votes", yes_votes)
            with col2:
                st.metric("No Votes", no_votes)

            # Calculate and display money line
            yes_ml, no_ml = calculate_money_line(yes_votes, no_votes)
            st.subheader("Money Line")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Yes Money Line", f"{yes_ml:.2f}")
            with col2:
                st.metric("No Money Line", f"{no_ml:.2f}")

            # Display all users
            st.subheader("Users in Room")
            for user, vote in room['users'].items():
                st.write(f"👤 {user}: {vote if vote else 'Hasn't voted yet'}")

if __name__ == "__main__":
    main()
