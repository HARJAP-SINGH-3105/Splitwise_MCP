"""
👋 Welcome to your Smithery project!
To run your server, use "uv run dev"
To test interactively, use "uv run playground"

You might find this resources useful:

🧑‍💻 MCP's Python SDK (helps you define your server)
https://github.com/modelcontextprotocol/python-sdk
"""

import os
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from smithery.decorators import smithery
from datetime import datetime, timedelta

# --- Config schema for user session ---
# class ConfigSchema(BaseSettings):
#     api_key: str = Field(..., description="Your Splitwise API key")
#     consumer_key: str = Field(..., description="Your Splitwise consumer key")
#     consumer_secret: str = Field(..., description="Your Splitwise consumer secret")

from pydantic_settings import BaseSettings, SettingsConfigDict

class ConfigSchema(BaseSettings):
    api_key: str
    consumer_key: str
    consumer_secret: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@smithery.server(config_schema=ConfigSchema)
def create_server() -> FastMCP:
    """Create and configure the Splitwise MCP server."""
    config = ConfigSchema()
    from splitwise import Splitwise
    from splitwise.group import Group
    from splitwise.user import User
    from splitwise.expense import Expense
    from splitwise.user import ExpenseUser

    # Warn if config is empty (during first launch without user input)
    if not config.api_key or not config.consumer_key or not config.consumer_secret:
        print("⚠️ Warning: Missing credentials, tools won’t work until configured.")

    server = FastMCP("Splitwise Tools")

    # ------------------------------------------------------------------
    @server.tool()
    def fetch_friends_data(ctx: Context):
        """Fetch list of all friends with balances."""
        try:
            sobj = Splitwise(config.consumer_key, config.consumer_secret, api_key=config.api_key)
            my_friends = sobj.getFriends()
            friend_list = []
            for friend in my_friends:
                name = friend.getFirstName()
                if friend.getLastName():
                    name += " " + friend.getLastName()
                friend_id = friend.getId()
                balance = friend.getBalances()[0].getAmount() if len(friend.getBalances()) else 0
                friend_list.append({"Name": name, "Id": friend_id, "Balance": balance})
            return friend_list
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    # ------------------------------------------------------------------
    @server.tool()
    def get_expenses_last_n_days(num_days: int, ctx: Context):
        """Retrieve expenses from the last `num_days` days."""
        try:
            sobj = Splitwise(config.consumer_key, config.consumer_secret, api_key=config.api_key)
            start_date = (datetime.today() - timedelta(days=num_days)).strftime("%Y-%m-%d")
            end_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
            expenses = sobj.getExpenses(dated_after=start_date, dated_before=end_date)

            all_exp = []
            for exp in expenses:
                dict_exp = {
                    "Id of Expense": exp.getId(),
                    "Description": exp.getDescription(),
                    "Cost(Expense)": exp.getCost(),
                    "Details of transaction": exp.getDetails(),
                    "Created by": exp.getCreatedBy().getFirstName(),
                    "Date of Expense": exp.getDate(),
                    "Currency code of transaction": exp.getCurrencyCode(),
                }
                try:
                    group = sobj.getGroup(exp.getGroupId())
                    dict_exp["Group Name"] = group.getName() if group else "Non-group expenses"
                except:
                    dict_exp["Group Name"] = "Non-group expenses"
                all_exp.append(dict_exp)

            return all_exp
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    # ------------------------------------------------------------------
    @server.tool()
    def create_splitwise_expense(participants: list[str], paid_by: str, amount: float, description: str, ctx: Context):
        """Create a new expense in Splitwise."""
        try:
            sobj = Splitwise(config.consumer_key, config.consumer_secret, api_key=config.api_key)

            expense = Expense()
            expense.setCurrencyCode("INR")
            expense.setCost(str(amount))
            expense.setDescription(description)

            contri = amount / len(participants)
            users_list = []

            # Build name→ID dictionary
            dict_info = {}
            me = sobj.getCurrentUser()
            dict_info[me.getFirstName()] = me.getId()
            for friend in sobj.getFriends():
                dict_info[friend.getFirstName()] = friend.getId()

            for item in participants:
                if item not in dict_info:
                    continue
                user = ExpenseUser()
                user.setId(dict_info[item])
                user.setPaidShare(str(amount) if item == paid_by else "0")
                user.setOwedShare(str(contri))
                users_list.append(user)

            expense.setUsers(users_list)
            expense, errors = sobj.createExpense(expense)

            if errors is None:
                return {"message": "Expense added successfully!", "expense_id": expense.getId()}
            return {"error": "Failed to add expense", "details": str(errors)}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    # ------------------------------------------------------------------
    @server.tool()
    def create_splitwise_group(group_name: str, first_names: list[str], last_names: list[str], emails: list[str], ctx: Context):
        """Create a new group and add users."""
        try:
            sobj = Splitwise(config.consumer_key, config.consumer_secret, api_key=config.api_key)
            group = Group()
            group.setName(group_name)
            group, errors = sobj.createGroup(group)
            if errors:
                return {"error": f"Failed to create group: {errors}"}

            added_users = []
            for i in range(len(first_names)):
                user = User()
                user.setFirstName(first_names[i])
                user.setLastName(last_names[i])
                user.setEmail(emails[i])
                success, user, errors = sobj.addUserToGroup(user, group.getId())
                if errors:
                    return {"error": f"Failed to add user {first_names[i]} {last_names[i]}: {errors}"}
                if success:
                    added_users.append({"Id": user.getId(), "Name": f"{first_names[i]} {last_names[i]}", "Email": emails[i]})
            return {"message": "Group created successfully", "group_id": group.getId(), "group_name": group.getName(), "members_added": added_users}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    return server
