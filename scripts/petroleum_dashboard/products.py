# Petroleum HS codes. Descriptions are CONFIRMED from the API response itself
# (cmdDesc), never asserted here - see the India HSN correction incident.
FOCUS = {
 "2709":   "crude",
 "271012": "gasoline/light oils",
 "271019": "middle+heavy distillates & base oils",
 "271020": "oils containing biodiesel",
 "271111": "LNG",
 "271112": "propane",
 "271113": "butanes",
 "271119": "other LPG",
 "271121": "natural gas, gaseous",
 "2712":   "petroleum jelly/waxes",
 "2713":   "petroleum coke/bitumen/residues",
 "2715":   "bituminous mixtures",
 "3403":   "lubricating preparations",
}
# Products used for bilateral pairing analysis (keeps call count sane)
PAIRING = ["2709","271012","271019","271112","271113","271119","3403","2713"]
REPORTERS=[(842,"USA"),(484,"Mexico"),(682,"Saudi Arabia"),(784,"UAE"),(634,"Qatar"),
           (414,"Kuwait"),(512,"Oman"),(48,"Bahrain"),(699,"India")]
GCC={682,784,634,414,512,48}
