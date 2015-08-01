import json
from items import *
from util import *
from modifiers import *
from abilities import *
import random
default_characteristics = {
	"strength": 5, #how hard you hit
	"vitality": 5, #how much hp you have
	"dexterity": 5, #how much energy you have, your position in turn qeue
	"intelligence": 5, #how likely you are to cause critical effects when attacking
}

default_equipment = {
	"armor": None,
	"primary_weapon": None,
	"secondary_weapon": None,
	"ring": None,
	"talisman": None,
	"headwear": None
}


class Creature(object):
	def __init__(self, name, level=1, characteristics = default_characteristics, stats=None, description=None, inventory=[], equipment=default_equipment, tags=[],abilities=[], modifiers = []):

		self.uid = get_uid()
		self.name = name
		self.description = description
		self.event = None
		self._level = level


		self.modifiers = modifiers.copy()
		self.base_characteristics = characteristics.copy()
		
		self.base_tags = tags.copy()
		self.base_abilities = abilities

		self.inventory = inventory.copy()
		self.equipment = equipment.copy()

		self.refresh_derived()
		self.dead = False

		

	def get_stats_from_characteristics(self, characteristics): #stats are completely derived from characteristics
		stats =  {
			"health": 0,
			"energy": 0,
			"max_health": 0,
			"max_energy": 0,
			"energy_regen": 0
		}

		stats["max_health"] = characteristics["vitality"]*10
		stats["max_energy"] = characteristics["dexterity"]
		stats["energy_regen"] = clamp(int(characteristics["dexterity"] / 3), 2, 10)
		stats["health"] = stats["max_health"]
		stats["energy"] = stats["max_energy"]
		return stats

	@property
	def health(self):
		return self.stats["health"]

	@health.setter
	def health(self, value):
		if value > self.stats["max_health"]:
			value = self.stats["max_health"]
		if value < 0:
			value = 0
		self.stats["health"] = value

	@property
	def energy(self):
		return self.stats["energy"]

	@energy.setter
	def energy(self, value):
		if value > self.stats["max_energy"]:
			value = self.stats["max_energy"]
		if value < 0:
			value = 0
		self.stats["energy"] = value

	@property
	def primary_weapon(self):
		return self.equipment["primary_weapon"]

	@primary_weapon.setter
	def primary_weapon(self, value):
		self.equipment["primary_weapon"] = value

	@property
	def armor(self):
		return self.equipment["armor"]

	@armor.setter
	def armor(self, value):
		self.equipment["armor"] = value

	@property
	def secondary_weapon(self):
		return self.equipment["secondary_weapon"]

	@secondary_weapon.setter
	def secondary_weapon(self, value):
		self.equipment["secondary_weapon"] = value

	@property
	def ring(self):
		return self.equipment["ring"]

	@ring.setter
	def ring(self, value):
		self.equipment["ring"] = value

	@property
	def talisman(self):
		return self.equipment["talisman"]

	@talisman.setter
	def talisman(self, value):
		self.equipment["talisman"] = value

	@property
	def headwear(self):
		return self.equipment["headwear"]

	@headwear.setter
	def headwear(self, value):
		self.equipment["headwear"] = value

	@property
	def defence(self):
		base_def = diceroll("1d1")
		defence = base_def
		for key in list(self.equipment.keys()):
			if self.equipment[key] and "defence" in list(self.equipment[key].stats.keys()):
				defence += diceroll(self.equipment[key].stats["defence"])

		for modifier in self.modifiers:
			if "defence" in modifier.stats_change:
				defence += diceroll(modifier.stats_change["defence"])

		#todo defence from level perks

		return defence

	@property
	def evasion(self):
		base_ev = diceroll(str(self.characteristics["dexterity"])+"d6")
		evasion = base_ev
		for key in list(self.equipment.keys()):
			if self.equipment[key] and "evasion" in list(self.equipment[key].stats.keys()):
				evasion += diceroll(self.equipment[key].stats["evasion"])

		for modifier in self.modifiers:
			if "evasion" in modifier.stats_change:
				evasion += diceroll(modifier.stats_change["evasion"])

		#todo evasion from level perks
		return evasion


	@property
	def level(self):
		return self._level

	@level.setter
	def level(self, value):
		self._level = value

	def damage(self, value):
		msg = ""
		if not self.dead:
			self.health = self.health - value
			msg += self.on_health_lost(value)
		return msg

	def equip(self, target_item):
		if target_item.item_type == "consumable":
			return "Can't equip %s."%(target_item.name)

		if self.equipment[target_item.item_type] == target_item:
			return "Already equipped %s."%(target_item.name)

		if self.equipment[target_item.item_type]:
			temp = self.equipment[target_item.item_type]
			self.unequip(temp)

		self.equipment[target_item.item_type] = target_item
		for item in self.inventory:
			if item == target_item:
				self.inventory.remove(item)
		self.refresh_derived()
		self.sort_inventory()
		msg = self.on_item_equipped(target_item)
		return msg + "Succesfully equipped %s."%(target_item.name)

	def unequip(self, target_item):
		if target_item.item_type == "consumable":
			return "Can't unequip %s."%(target_item.name)
		if self.equipment[target_item.item_type] == target_item:
			self.equipment[target_item.item_type] = None
			self.inventory.append(target_item)
			self.sort_inventory()
			self.refresh_derived()
			msg = self.on_item_unequipped(target_item)
			return msg + "Succesfully unequipped %s."%(target_item.name)
		return "Not equipped!"

	def destroy(self, target_item):
		if target_item in self.inventory:
			self.unequip(target_item)
			#for item in self.inventory:
			#	if item == target_item:
			self.inventory.remove(target_item)
			self.sort_inventory()
			return "Succesfully destroyed %s."%(target_item.name)
		return "No such item."

	def use(self, item):
		if item in self.inventory:
			use_effect = item.use(self)
			msg = self.on_consumable_used(item)
			self.sort_inventory()
			return use_effect + msg

	def add_modifier(self, modifier):
		self.modifiers.append(modifier)
		self.modifiers = sorted(self.modifiers, key=lambda x: x.priority, reverse=False)

	""" EVENTS """
	def on_combat_start(self):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_combat_start()
			if effect:
				msg += effect
		return msg

	def on_combat_over(self):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_combat_over()
			if effect:
				msg += effect
		self.energy = self.stats["max_energy"]
		return msg

	def on_round(self):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_round()
			if effect:
				msg += effect

		if not self.dead:
			self.energy += self.stats["energy_regen"]
			msg += self.on_energy_gained(self.stats["energy_regen"])
		return msg

	def on_turn(self):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_turn()
			if effect:
				msg += effect

		return msg

	def on_modifier_applied(self, modifier):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_modifier_applied(modifier)
			if effect:
				msg += effect
		return msg

	def on_experience_gained(self, value):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_experience_gained(value)
			if effect:
				msg += effect
		return msg

	def on_item_equipped(self, item):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_item_equipped(item)
			if effect:
				msg += effect
		return msg

	def on_item_unequipped(self, item):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_item_unequipped(item)
			if effect:
				msg += effect
		return msg

	def on_consumable_used(self, item):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_consumable_used(item)
			if effect:
				msg += effect
		return msg


	def on_health_lost(self, value):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_health_lost(value)
			if effect:
				msg += effect
		return msg

	def on_health_gained(self, value):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_health_gained(value)
			if effect:
				msg += effect
		return msg

	def on_energy_gained(self, value):
		#msg = "%s gains %d energy.\n"%(self.name.title(), value)
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_energy_gained(value)
			if effect:
				msg += effect
		return msg

	def on_energy_lost(self, value):
		msg = ""
		for modifier in self.modifiers:
			effect = modifier.on_energy_lost(value)
			if effect:
				msg += effect
		return msg

	def on_attacked(self, attack_info):
		msg = ""
		if attack_info.use_info["damage_dealt"] > 0:
			attack_info.description += self.damage(attack_info.use_info["damage_dealt"])

		for modifier in self.modifiers:
			at_info = modifier.on_attacked(attack_info)
			if at_info:
				attack_info = at_info

		attack_info = self.kill_if_nececary(attack_info) 
		return attack_info

	def on_attack(self, attack_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_attack(attack_info)
			if at_info:
				attack_info = at_info
		return attack_info

	def on_kill(self, attack_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_kill(attack_info)
			if at_info:
				attack_info = at_info
		
		return attack_info

	def on_death(self, attack_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_death(attack_info)
			if at_info:
				attack_info = at_info
		return attack_info

	def on_miss(self, attack_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_miss(attack_info)
			if at_info:
				attack_info = at_info
		return attack_info

	def on_buffed(self, ability_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_buffed(ability_info)
			if at_info:
				ability_info = at_info
		return ability_info

	def on_buff(self, ability_info):
		msg = ""
		for modifier in self.modifiers:
			at_info = modifier.on_buff(ability_info)
			if at_info:
				ability_info = at_info
		return ability_info


	""" /EVENTS """
	def kill_if_nececary(self, attack_info):
		if self.health <= 0:
			attack_info = self.die(attack_info)
			return attack_info
		return attack_info

	def die(self, attack_info):
		self.dead = True
		attack_info.use_info["did_kill"] = True
		attack_info.description += "%s is killed by %s.\n"%(self.name.title(), attack_info.inhibitor.name)
		attack_info = attack_info.inhibitor.on_kill(attack_info)
		attack_info = self.on_death(attack_info)
		return attack_info

	def examine_equipment(self):
		#desc = "%s's equipment:\n"%(self.name)
		desc = ""

		if self.primary_weapon:
			desc+="|\t%s: %s.\n"%("Primary weapon", self.primary_weapon.short_desc)
		if self.secondary_weapon:
			desc+="|\t%s: %s.\n"%("Secondary weapon", self.secondary_weapon.short_desc)
		if self.armor:
			desc+="|\t%s: %s.\n"%("Armor", self.armor.short_desc)
		if self.headwear:
			desc+="|\t%s: %s.\n"%("Headwear", self.armor.short_desc)
		if self.ring:
			desc+="|\t%s: %s.\n"%("Ring", self.ring.short_desc)
		if self.talisman:
			desc+="|\t%s: %s.\n"%("Talisman", self.talisman.short_desc)

		return desc

	def sort_inventory(self):
		inv = {
			"primary_weapon" :[],
			"secondary_weapon" :[],
			"armor" :[],
			"headwear" :[],
			"talisman" :[],
			"ring" :[],
			"consumable" :[],
		}
		for item in self.inventory:
			inv[item.item_type].append(item)

		for key in list(inv.keys()):
			inv[key] = sorted(inv[key], key=lambda item: item.name)

		self.inventory = inv["primary_weapon"] + inv["secondary_weapon"] + inv["armor"] + inv["headwear"] + inv["talisman"] + inv["ring"] + inv["consumable"]

	def examine_inventory(self):
		#desc = "%s's inventory:\n"%(self.name)
		self.sort_inventory()
		desc = ""
		items = []
		for i in range(len(self.inventory)):
			item = self.inventory[i]
			if item:
				items.append(str(i+1)+"."+item.short_desc)
		return desc + ', '.join(items)

	def refresh_tags(self):
		self.tags = self.base_tags.copy()
		if hasattr(self, "level_perks"):
			for perk in self.level_perks:
				for tag in perk.tags_granted:
					self.tags.append(tag)

		for modifier in self.modifiers:
			for tag in modifier.tags_granted:
				self.tags.append(tag)

		for key in list(self.equipment.keys()):
			if self.equipment[key]:
				for tag in self.equipment[key].tags_granted:
					self.tags.append(tag)

	def refresh_modifiers(self):
		self.modifiers = []
		if hasattr(self, "level_perks"):
			for perk in self.level_perks:
				for modifier in perk.modifiers_granted:
					modifier_object = get_modifier_by_name( modifier["name"], perk, self, modifier["params"] )
					modifier_object.apply()

		for key in self.equipment.keys():
			if self.equipment[key]:
				for modifier in self.equipment[key].modifiers_granted:
					modifier_object = get_modifier_by_name( modifier["name"], self.equipment[key], self, modifier["params"] )
					modifier_object.apply()

	def refresh_abilities(self):
		self.abilities = self.base_abilities.copy()
		if hasattr(self, "level_perks"):
			for perk in self.level_perks:
				for ability in perk.abilities_granted:
					prototype = abilities[ability]
					self.abilities.append(prototype(ability, perk))

		for modifier in self.modifiers:
			for ability in modifier.abilities_granted:
				prototype = abilities[ability]
				self.abilities.append(prototype(ability, modifier))

		for key in self.equipment.keys():
			if self.equipment[key]:
				for ability in self.equipment[key].abilities_granted:
					prototype = abilities[ability]
					self.abilities.append(prototype(ability, self.equipment[key]))

	def refresh_derived(self):
		self.refresh_modifiers()
		self.refresh_abilities()
		self.refresh_tags()
		self.characteristics = self.base_characteristics.copy()
		#refresh characteristics
		if hasattr(self, "level_perks"):
			for perk in self.level_perks:
				for characteristic in list(perk.characteristics_change.keys()):
					self.characteristics[characteristic] += perk.characteristics_change[characteristic]

		for modifier in self.modifiers:
			for characteristic in list(modifier.characteristics_change.keys()):
					self.characteristics[characteristic] += modifier.characteristics_change[characteristic]
		
		for item in list(self.equipment.keys()):
			if self.equipment[item] and "characteristics_change" in list(self.equipment[item].stats.keys()):
				for characteristic in list(self.equipment[item].stats["characteristics_change"].keys()):
					self.characteristics[characteristic] += self.equipment[item].stats["characteristics_change"][characteristic]

		self.stats = self.get_stats_from_characteristics(self.characteristics)
		#refresh stats
		if hasattr(self, "level_perks"):
			for perk in self.level_perks:
				for stat in list(perk.stats_change.keys()):
					self.stats[stat] += perk.stats_change[stat]

		for modifier in self.modifiers:
			for stat in list(modifier.stats_change.keys()):
					self.stats[stat] += modifier.stats_change[stat]
		
		for item in list(self.equipment.keys()):
			if self.equipment[item] and "stats_change" in list(self.equipment[item].stats.keys()):
				for stat in list(self.equipment[item].stats["stats_change"].keys()):
					self.stats[stat] += self.equipment[item].stats["stats_change"][stat]

	def examine_self(self):
		desc = "\n".join(
		[
			"%s. lvl %d"%(self.name.title(), self.level),
			"%s"%(self.description or "----"),
			"Characteristics:\n%s\n"%("\n".join(["|\t"+x+":" +str(self.characteristics[x]) for x in list(self.characteristics.keys())])),
			"Health:\n|\t%d/%d"%(self.health, self.stats["max_health"]),
			"Energy:\n|\t%d/%d, regen per turn: %d"%(self.energy, self.stats["max_energy"],self.stats["energy_regen"]) + "\nExp:\n|\t%d/%d"%(self.experience, self.max_experience) if hasattr(self, "experience") else "",
			"Tags:\n|\t%s"%(", ".join(self.tags)),
			"Modifiers:\n|\t%s"%(", ".join(["%s(%s)"%(modifier.name, modifier.granted_by.name) for modifier in self.modifiers])),
			"Abilities:\n|\t%s"%(", ".join(["%s(%s)"%(abiility.name, abiility.granted_by.name) for abiility in self.abilities])),
			"Equipment:\n"+self.examine_equipment()
		])
		return desc

	def to_json(self):
		big_dict = self.__dict__.copy()
		del big_dict["uid"]
		big_dict["characteristics"] = self.base_characteristics.copy()
		# big_dict["tags"] = json.dumps(self.tags)
		big_dict["tags"] = self.base_tags
		del big_dict["base_tags"]
		del big_dict["abilities"] #abilities are not serializable
		del big_dict["modifiers"] #modifiers are derived so no point in serializing them
		big_dict["inventory"] = []
		for item in self.inventory:
			big_dict["inventory"].append(item.to_json())
		big_dict["equipment"] = default_equipment.copy()
		for key in self.equipment:
			if self.equipment[key]:
				big_dict["equipment"][key] = self.equipment[key].to_json()
		#big_dict["equipment"] = json.dumps(big_dict["equipment"])
		return big_dict

class Player(Creature):
	def __init__(self, username, name, level=1, characteristics = default_characteristics, stats=None, description=None, inventory=[], equipment=default_equipment, tags=["animate", "humanoid", "human"],abilities=[],modifiers=[], level_perks=[], experience=0, max_experience=1000):
		self.level_perks = level_perks.copy()
		self._experience = experience
		self.max_experience = max_experience
		self.username = username

		Creature.__init__(self, name, level, characteristics, stats, description, inventory, equipment, tags, abilities, modifiers)

	@property
	def experience(self):
		return self._experience

	@experience.setter
	def experience(self, value):
		if value > self.max_experience:
			over_cur_level = value - (self.max_experience - self.experience)
			self.level = self.level +  1
			self.experience = over_cur_level
		else:
			self._experience = value

	@property
	def level(self):
		return self._level

	@level.setter
	def level(self, value):
		self._level = value
		self.max_experience = value * 1000

	def examine_self(self):
		desc = super(Player, self).examine_self()
		return desc

	@staticmethod
	def de_json(data):
		if isinstance(data, str):
			data = json.loads(data)
		stats = None
		if "stats" in list(data.keys()):
			stats = data["stats"]
			if isinstance(data["stats"], str):
				data["stats"] = json.loads(data["stats"])
				stats = data["stats"]

		for i in range(len(data["inventory"])):
			data["inventory"][i] = Item.de_json(data["inventory"][i])

		equipment = default_equipment.copy()
		eq = data["equipment"]
		for key in list(eq.keys()):
			if eq[key]:
				equipment[key] = Item.de_json(eq[key])

		data["equipment"] = equipment
		ply = Player(data.get("username"), data.get("name"), data.get("_level"), data.get("characteristics"), stats, data.get("description"), data.get("inventory"), data.get("equipment"), data.get('tags'), [], [], data.get("level_perks"), data.get("_experience"), data.get("max_experience"))
		return ply

	def on_kill(self, attack_info):
		target = attack_info.target
		if isinstance(target, Enemy):
			attack_info.use_info["experience_gained"] = target.exp_value
			attack_info.description += "%s earns %d experience.\n"%(attack_info.inhibitor.name, target.exp_value)
			attack_info.description += attack_info.inhibitor.on_experience_gained(target.exp_value)
			drop_table = target.__class__.drop_table
			for item in list(drop_table.keys()):
				prob = int(drop_table[item])
				got_item = random.randint(0, 100) <= prob 
				if got_item:
					item = get_item_by_name(item, target.__class__.loot_coolity)
					attack_info.use_info["loot_dropped"].append(item)
					if isinstance(attack_info.inhibitor, Player):
						attack_info.inhibitor.inventory.append(item)
					attack_info.use_info["loot_dropped"].append(item)
					attack_info.description += "%s got loot: %s.\n"%(attack_info.inhibitor.name.title(), item.name)
		return super(Player, self).on_kill(attack_info)
			
	def to_json(self):
		big_dict = super(Player, self).to_json()
		big_dict["username"] = self.username
		big_dict["event"] = None
		return big_dict

	def __str__(self):
		return self.examine_self()

class Enemy(Creature):

	loot_coolity = 0

	drop_table = {

	}

	def __init__(self, name, level=1, characteristics = default_characteristics, stats=None, description=None, inventory=[], equipment=default_equipment, tags=[],abilities=[],modifiers=[], exp_value=0):
		Creature.__init__(self, name, level, characteristics, stats, description, inventory, equipment, tags, abilities, modifiers)
		self.exp_value = exp_value

	def act(self):
		return "Base enemy has no AI"

	def die(self, attack_info):
		attack_info = super(Enemy, self).die(attack_info)

		return attack_info

	@staticmethod
	def de_json(data):
		data["characteristics"] = json.loads(data["characteristics"])

		stats = None
		if "stats" in list(data.keys()):
			data["stats"] = json.loads(data["stats"])
			stats = data["stats"]
					
		for i in range(len(data["inventory"])):
			data["inventory"][i] = Item.de_json(data["inventory"][i])

		equipment = default_equipment.copy()
		eq = data["equipment"]
		for key in list(eq.keys()):
			if eq[key]:
				equipment[key] = Item.de_json(eq[key])
		data["equipment"] = equipment

		en =  Enemy(data.get("name"), data.get("level"), data.get("characteristics"), stats, data.get("description"), inventory, equipment, data.get('tags'), [], [])
		return en

