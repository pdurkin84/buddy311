var buddy311buttonClick = function () {
	console.log("Buddy311 button pressed");
	var docElement = document.getElementById('myTextBox');
	var results="";
	if ( docElement.value == "" ) {
		console.log("Manual entry not updated or empty: ", docElement.value);
		docElement = document.getElementById('final_span');
		if (docElement.innerText == "" ) {
			console.log("final span empty, checking interim span");
			docElement = document.getElementById('interim_span');
		
			if (docElement.innerText == "" ) {
				console.log("No text, ignoring");
				// for testing purposes remove the return here so that it continues to get classifications
				// return;
			} else {
				results = docElement.innerText;
			}
		} else {
			results = docElement.innerText;
		}
	} else {
		results = docElement.value;
	}
	
	console.log("Received text: ", results);
	xhttp = new XMLHttpRequest();
	// Function called when data returns
	xhttp.onreadystatechange = function(d) {
		if (this.readyState != 4 ) {
			// State is not done
			return;
		}
		console.log("Statechange function called: ", this.responseText);
		if (this.responseText != "") {
			typeText = JSON.parse(this.responseText);
			console.log("The json value is : ", typeText);

			var fspan = document.getElementById('final_span');
			fspan.innerHTML+="<br><p><br><strong><font color=\"red\"> Type: </font>" + typeText['service_code'] + "</strong>";
		//	var typeLocation = document.getElementById('returnclass-type');
		//	typeLocation.innerHTML="<strong><font color=\"red\"> Type: </font></strong>" + typeText['service_code'];
		//	typeLocation.style.visibility = "visible";
		}
	}
//	xhttp.open("POST", "https://169.63.3.124:31102/buddy311/v0.1/", true);
	xhttp.open("POST", "https://169.63.3.115:31102/buddy311/v0.1/", true);
//	xhttp.open("POST", "https://buddy311.org:31102/buddy311/v0.1/", true);
	xhttp.setRequestHeader("Content-type", "application/json");
	xhttp.send('{ "description":"' + results + '", "service_code": "unknown" }');
}
