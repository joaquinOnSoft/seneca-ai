You are a Python developer.

We are going a create a Python application called Seneca-AI

# What is Seneca-AI?
 - Seneca-AI, hereinafter referred to as Seneca, is a European open-source generative AI project.
 - It is multi-purpose and cross-platform.
 - It is an assistant/guide created by and for humans.
 - It supports and empowers, but does not eliminate or replace.

# Screens

## Main screen

Main window includes a:

- Application title: "Seneca AI"
- Top left corner: hamburger icon. When is clicked the lateral menu is shown.
- Left-hand side menu (Lateral menu) is hiden by default. When is shown includes the following items:
	- New conversation: when clicked the AI model context is cleaned/restarted
	- Conversations: Shows the title of the latest 20 conversations
- The text box for entering the user’s request is located in the bottom-right corner. It takes up 90% of the horizontal space, leaving a 10-pixel margin on the right.
- The text box for entering the user’s request is located in the bottom-right corner. It takes up 90% of the horizontal space, leaving a 10-pixel margin on the right, and 15% of the vertical space, leaving a 10-pixel bottom margin.
Inside it, there are two icons:
	- A microphone, for converting the user’s spoken prompt into text
	- A triangle/play icon, for executing the prompt entered by the user. When the play icon is clicked is replaced by a stop/square rectangle to indicate that Seneca is thinking. If the user click on the stop icon the Seneca request is canceled. Once the request is completed the text box is cleared.
The prompt text must not overlap with the icons

Each prompt entered by the user, once the play icon has been clicked, is displayed in a speech bubble with the arrow pointing to the right, starting from the top.

Seneca AI’s response is displayed below the user’s prompt, in a speech bubble with the arrow pointing to the right.

The conversation bubbles take up the top 85%. If necessary, vertical scrolling will be allowed in the area reserved for the conversation bubbles.

All the text literal are supported in 4 languages: Spanish, English, French and Portuguese. If user language is not supported, english will be used as default language.

Screen mockups uploaded for reference.

# Python libraries

Use the following libraries to generate the code:

- customtkinter: A modern and customizable python UI-library based on Tkinter: 
[customtkinter](https://customtkinter.tomschimansky.com)
- LangChain: provides the engineering platform and open source frameworks developers use to build, test, and deploy reliable AI agents.
- python-dotenv: reads key-value pairs from a .env file and can set them as environment variables. It helps in the development of applications following the 12-factor principles.
- Babel: A collection of tools for internationalizing Python applications.

Always use the latest stable version of each library available.

# Code conventions

Follow PEP 8 for formatting, use 4 spaces for indentation, and name functions with snake_case. Limit lines to 79 characters, use docstrings for modules and functions, and organize imports in standard order. Apply type hints where they add clarity.

# Project structure

Separate code into modules by responsibility, use a src/ or package directory for your code, and add tests in a parallel structure. Include a README.md, requirements.txt, and a .gitignore. Keep configuration separate from code.

# Pythonic code

Pythonic code follows Python’s philosophy of readability and simplicity. It uses built-in features like list comprehensions, context managers, and iterators instead of patterns from other languages. Code that is Pythonic feels natural to experienced Python developers.

Reference: 
 - [Python Best Practices for More Pythonic Code](https://realpython.com/tutorials/best-practices/)