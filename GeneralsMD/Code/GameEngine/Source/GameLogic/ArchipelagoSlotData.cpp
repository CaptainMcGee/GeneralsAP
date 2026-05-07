/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 Electronic Arts Inc.
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "PreRTS.h"

#include "GameLogic/ArchipelagoSlotData.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>
#include <string>

static const char* kExpectedLogicModel = "generalszh-alpha-grouped-v1";
static const Int kExpectedSlotDataVersion = 2;

static std::string toLowerCopy( const std::string& value )
{
	std::string out = value;
	for ( size_t i = 0; i < out.size(); ++i )
		out[i] = (char)std::tolower( (unsigned char)out[i] );
	return out;
}

static Bool asciiEqualsNoCase( const AsciiString& lhs, const char* rhs )
{
	return lhs.compareNoCase( rhs ) == 0;
}

static Bool startsWith( const std::string& value, const char* prefix )
{
	const size_t len = std::strlen( prefix );
	return value.size() >= len && value.compare( 0, len, prefix ) == 0;
}

struct JsonValue
{
	enum Type
	{
		JSON_NULL,
		JSON_BOOL,
		JSON_NUMBER,
		JSON_STRING,
		JSON_ARRAY,
		JSON_OBJECT
	};

	Type type;
	Bool boolValue;
	double numberValue;
	std::string stringValue;
	std::vector<JsonValue> arrayValue;
	std::map<std::string, JsonValue> objectValue;

	JsonValue() : type( JSON_NULL ), boolValue( FALSE ), numberValue( 0.0 ) {}

	const JsonValue* get( const char* key ) const
	{
		if ( type != JSON_OBJECT )
			return NULL;
		std::map<std::string, JsonValue>::const_iterator it = objectValue.find( key );
		return it == objectValue.end() ? NULL : &it->second;
	}
};

class JsonParser
{
public:
	JsonParser( const std::string& text ) : m_text( text ), m_pos( 0 ) {}

	Bool parse( JsonValue& out, std::string& error )
	{
		skipWhitespace();
		if ( !parseValue( out, error ) )
			return FALSE;
		skipWhitespace();
		if ( m_pos != m_text.size() )
		{
			error = "unexpected trailing JSON content";
			return FALSE;
		}
		return TRUE;
	}

private:
	void skipWhitespace()
	{
		while ( m_pos < m_text.size() && std::isspace( (unsigned char)m_text[m_pos] ) )
			++m_pos;
	}

	Bool parseValue( JsonValue& out, std::string& error )
	{
		skipWhitespace();
		if ( m_pos >= m_text.size() )
		{
			error = "unexpected end of JSON";
			return FALSE;
		}

		const char ch = m_text[m_pos];
		if ( ch == '{' )
			return parseObject( out, error );
		if ( ch == '[' )
			return parseArray( out, error );
		if ( ch == '"' )
		{
			out.type = JsonValue::JSON_STRING;
			return parseString( out.stringValue, error );
		}
		if ( ch == '-' || std::isdigit( (unsigned char)ch ) )
			return parseNumber( out, error );
		if ( m_text.compare( m_pos, 4, "true" ) == 0 )
		{
			m_pos += 4;
			out.type = JsonValue::JSON_BOOL;
			out.boolValue = TRUE;
			return TRUE;
		}
		if ( m_text.compare( m_pos, 5, "false" ) == 0 )
		{
			m_pos += 5;
			out.type = JsonValue::JSON_BOOL;
			out.boolValue = FALSE;
			return TRUE;
		}
		if ( m_text.compare( m_pos, 4, "null" ) == 0 )
		{
			m_pos += 4;
			out.type = JsonValue::JSON_NULL;
			return TRUE;
		}

		error = "unexpected JSON token";
		return FALSE;
	}

	Bool parseObject( JsonValue& out, std::string& error )
	{
		out = JsonValue();
		out.type = JsonValue::JSON_OBJECT;
		++m_pos;
		skipWhitespace();
		if ( m_pos < m_text.size() && m_text[m_pos] == '}' )
		{
			++m_pos;
			return TRUE;
		}

		while ( m_pos < m_text.size() )
		{
			std::string key;
			if ( m_text[m_pos] != '"' || !parseString( key, error ) )
				return FALSE;
			skipWhitespace();
			if ( m_pos >= m_text.size() || m_text[m_pos] != ':' )
			{
				error = "expected ':' in JSON object";
				return FALSE;
			}
			++m_pos;
			JsonValue value;
			if ( !parseValue( value, error ) )
				return FALSE;
			out.objectValue[key] = value;
			skipWhitespace();
			if ( m_pos < m_text.size() && m_text[m_pos] == '}' )
			{
				++m_pos;
				return TRUE;
			}
			if ( m_pos >= m_text.size() || m_text[m_pos] != ',' )
			{
				error = "expected ',' or '}' in JSON object";
				return FALSE;
			}
			++m_pos;
			skipWhitespace();
		}

		error = "unterminated JSON object";
		return FALSE;
	}

	Bool parseArray( JsonValue& out, std::string& error )
	{
		out = JsonValue();
		out.type = JsonValue::JSON_ARRAY;
		++m_pos;
		skipWhitespace();
		if ( m_pos < m_text.size() && m_text[m_pos] == ']' )
		{
			++m_pos;
			return TRUE;
		}

		while ( m_pos < m_text.size() )
		{
			JsonValue value;
			if ( !parseValue( value, error ) )
				return FALSE;
			out.arrayValue.push_back( value );
			skipWhitespace();
			if ( m_pos < m_text.size() && m_text[m_pos] == ']' )
			{
				++m_pos;
				return TRUE;
			}
			if ( m_pos >= m_text.size() || m_text[m_pos] != ',' )
			{
				error = "expected ',' or ']' in JSON array";
				return FALSE;
			}
			++m_pos;
			skipWhitespace();
		}

		error = "unterminated JSON array";
		return FALSE;
	}

	Bool parseString( std::string& out, std::string& error )
	{
		if ( m_pos >= m_text.size() || m_text[m_pos] != '"' )
		{
			error = "expected JSON string";
			return FALSE;
		}
		++m_pos;
		out.clear();
		while ( m_pos < m_text.size() )
		{
			char ch = m_text[m_pos++];
			if ( ch == '"' )
				return TRUE;
			if ( ch != '\\' )
			{
				out.push_back( ch );
				continue;
			}
			if ( m_pos >= m_text.size() )
			{
				error = "unterminated JSON escape";
				return FALSE;
			}
			const char esc = m_text[m_pos++];
			switch ( esc )
			{
				case '"': out.push_back( '"' ); break;
				case '\\': out.push_back( '\\' ); break;
				case '/': out.push_back( '/' ); break;
				case 'b': out.push_back( '\b' ); break;
				case 'f': out.push_back( '\f' ); break;
				case 'n': out.push_back( '\n' ); break;
				case 'r': out.push_back( '\r' ); break;
				case 't': out.push_back( '\t' ); break;
				case 'u':
					if ( m_pos + 4 > m_text.size() )
					{
						error = "bad JSON unicode escape";
						return FALSE;
					}
					// Slot-data keys/templates are ASCII. Preserve non-ASCII as '?' for safety.
					out.push_back( '?' );
					m_pos += 4;
					break;
				default:
					error = "bad JSON escape";
					return FALSE;
			}
		}
		error = "unterminated JSON string";
		return FALSE;
	}

	Bool parseNumber( JsonValue& out, std::string& error )
	{
		const size_t start = m_pos;
		if ( m_text[m_pos] == '-' )
			++m_pos;
		while ( m_pos < m_text.size() && std::isdigit( (unsigned char)m_text[m_pos] ) )
			++m_pos;
		if ( m_pos < m_text.size() && m_text[m_pos] == '.' )
		{
			++m_pos;
			while ( m_pos < m_text.size() && std::isdigit( (unsigned char)m_text[m_pos] ) )
				++m_pos;
		}
		if ( m_pos < m_text.size() && ( m_text[m_pos] == 'e' || m_text[m_pos] == 'E' ) )
		{
			++m_pos;
			if ( m_pos < m_text.size() && ( m_text[m_pos] == '-' || m_text[m_pos] == '+' ) )
				++m_pos;
			while ( m_pos < m_text.size() && std::isdigit( (unsigned char)m_text[m_pos] ) )
				++m_pos;
		}
		if ( start == m_pos )
		{
			error = "bad JSON number";
			return FALSE;
		}
		out.type = JsonValue::JSON_NUMBER;
		out.numberValue = std::atof( m_text.substr( start, m_pos - start ).c_str() );
		return TRUE;
	}

	const std::string& m_text;
	size_t m_pos;
};

static Bool readRequiredString( const JsonValue& obj, const char* key, AsciiString& out, std::string& error )
{
	const JsonValue* value = obj.get( key );
	if ( value == NULL || value->type != JsonValue::JSON_STRING || value->stringValue.empty() )
	{
		error = std::string( "missing string field " ) + key;
		return FALSE;
	}
	out = AsciiString( value->stringValue.c_str() );
	return TRUE;
}

static Bool readOptionalString( const JsonValue& obj, const char* key, AsciiString& out )
{
	const JsonValue* value = obj.get( key );
	if ( value == NULL || value->type == JsonValue::JSON_NULL )
	{
		out.clear();
		return TRUE;
	}
	if ( value->type != JsonValue::JSON_STRING )
		return FALSE;
	out = AsciiString( value->stringValue.c_str() );
	return TRUE;
}

static Bool readRequiredInt( const JsonValue& obj, const char* key, Int& out, std::string& error )
{
	const JsonValue* value = obj.get( key );
	if ( value == NULL || value->type != JsonValue::JSON_NUMBER )
	{
		error = std::string( "missing numeric field " ) + key;
		return FALSE;
	}
	out = (Int)value->numberValue;
	return TRUE;
}

static Bool readOptionalInt( const JsonValue& obj, const char* key, Int& out, Bool& present )
{
	const JsonValue* value = obj.get( key );
	present = FALSE;
	if ( value == NULL || value->type == JsonValue::JSON_NULL )
		return TRUE;
	if ( value->type != JsonValue::JSON_NUMBER )
		return FALSE;
	out = (Int)value->numberValue;
	present = TRUE;
	return TRUE;
}

static Bool readRequiredReal( const JsonValue& obj, const char* key, Real& out, std::string& error )
{
	const JsonValue* value = obj.get( key );
	if ( value == NULL || value->type != JsonValue::JSON_NUMBER )
	{
		error = std::string( "missing numeric field " ) + key;
		return FALSE;
	}
	out = (Real)value->numberValue;
	return TRUE;
}

static Bool readOptionalReal( const JsonValue& obj, const char* key, Real& out, Bool& present )
{
	const JsonValue* value = obj.get( key );
	present = FALSE;
	if ( value == NULL || value->type == JsonValue::JSON_NULL )
		return TRUE;
	if ( value->type != JsonValue::JSON_NUMBER )
		return FALSE;
	out = (Real)value->numberValue;
	present = TRUE;
	return TRUE;
}

static Bool readFileBytes( const AsciiString& filePath, std::vector<unsigned char>& bytes )
{
	std::ifstream file( filePath.str(), std::ios::binary );
	if ( !file.is_open() )
		return FALSE;
	bytes.assign( std::istreambuf_iterator<char>( file ), std::istreambuf_iterator<char>() );
	return TRUE;
}

static UnsignedInt rotr32( UnsignedInt value, UnsignedInt count )
{
	return ( value >> count ) | ( value << ( 32u - count ) );
}

static void sha256Bytes( const std::vector<unsigned char>& data, unsigned char out[32] )
{
	static const UnsignedInt k[64] = {
		0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
		0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
		0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
		0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
		0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
		0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
		0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
		0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
	};

	UnsignedInt h[8] = {
		0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
		0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
	};

	std::vector<unsigned char> msg = data;
	const unsigned long long bitLen = (unsigned long long)msg.size() * 8ull;
	msg.push_back( 0x80u );
	while ( ( msg.size() % 64u ) != 56u )
		msg.push_back( 0u );
	for ( Int i = 7; i >= 0; --i )
		msg.push_back( (unsigned char)( ( bitLen >> ( i * 8 ) ) & 0xffu ) );

	for ( size_t chunk = 0; chunk < msg.size(); chunk += 64 )
	{
		UnsignedInt w[64];
		for ( Int i = 0; i < 16; ++i )
		{
			const size_t p = chunk + (size_t)i * 4u;
			w[i] = ( (UnsignedInt)msg[p] << 24 ) | ( (UnsignedInt)msg[p + 1] << 16 ) | ( (UnsignedInt)msg[p + 2] << 8 ) | (UnsignedInt)msg[p + 3];
		}
		for ( Int i = 16; i < 64; ++i )
		{
			const UnsignedInt s0 = rotr32( w[i - 15], 7 ) ^ rotr32( w[i - 15], 18 ) ^ ( w[i - 15] >> 3 );
			const UnsignedInt s1 = rotr32( w[i - 2], 17 ) ^ rotr32( w[i - 2], 19 ) ^ ( w[i - 2] >> 10 );
			w[i] = w[i - 16] + s0 + w[i - 7] + s1;
		}

		UnsignedInt a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
		for ( Int i = 0; i < 64; ++i )
		{
			const UnsignedInt s1 = rotr32( e, 6 ) ^ rotr32( e, 11 ) ^ rotr32( e, 25 );
			const UnsignedInt ch = ( e & f ) ^ ( ( ~e ) & g );
			const UnsignedInt temp1 = hh + s1 + ch + k[i] + w[i];
			const UnsignedInt s0 = rotr32( a, 2 ) ^ rotr32( a, 13 ) ^ rotr32( a, 22 );
			const UnsignedInt maj = ( a & b ) ^ ( a & c ) ^ ( b & c );
			const UnsignedInt temp2 = s0 + maj;
			hh = g;
			g = f;
			f = e;
			e = d + temp1;
			d = c;
			c = b;
			b = a;
			a = temp1 + temp2;
		}
		h[0] += a; h[1] += b; h[2] += c; h[3] += d;
		h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
	}

	for ( Int i = 0; i < 8; ++i )
	{
		out[i * 4 + 0] = (unsigned char)( ( h[i] >> 24 ) & 0xffu );
		out[i * 4 + 1] = (unsigned char)( ( h[i] >> 16 ) & 0xffu );
		out[i * 4 + 2] = (unsigned char)( ( h[i] >> 8 ) & 0xffu );
		out[i * 4 + 3] = (unsigned char)( h[i] & 0xffu );
	}
}

ArchipelagoSlotData::ArchipelagoSlotData()
{
	reset();
}

void ArchipelagoSlotData::reset()
{
	m_loaded = FALSE;
	m_version = 0;
	m_logicModel.clear();
	m_seedId.clear();
	m_slotName.clear();
	m_sessionNonce.clear();
	m_slotDataPath.clear();
	m_slotDataHash.clear();
	m_maps.clear();
	m_runtimeKeys.clear();
	m_missionRuntimeKeys.clear();
}

Bool ArchipelagoSlotData::computeFileSha256( const AsciiString& filePath, AsciiString& outHash )
{
	std::vector<unsigned char> bytes;
	if ( !readFileBytes( filePath, bytes ) )
		return FALSE;

	unsigned char digest[32];
	sha256Bytes( bytes, digest );

	static const char* hex = "0123456789abcdef";
	std::string text( "sha256:" );
	text.reserve( 71 );
	for ( Int i = 0; i < 32; ++i )
	{
		text.push_back( hex[( digest[i] >> 4 ) & 0x0f] );
		text.push_back( hex[digest[i] & 0x0f] );
	}
	outHash = AsciiString( text.c_str() );
	return TRUE;
}

AsciiString ArchipelagoSlotData::mapKeyForGeneralIndex( Int generalIndex )
{
	switch ( generalIndex )
	{
		case 0: return AsciiString( "air_force" );
		case 1: return AsciiString( "laser" );
		case 2: return AsciiString( "superweapon" );
		case 3: return AsciiString( "tank" );
		case 5: return AsciiString( "nuke" );
		case 6: return AsciiString( "toxin" );
		case 8: return AsciiString( "stealth" );
		default: return AsciiString::TheEmptyString;
	}
}

AsciiString ArchipelagoSlotData::mapLeafNameForKey( const AsciiString& mapKey )
{
	if ( asciiEqualsNoCase( mapKey, "air_force" ) )
		return AsciiString( "GC_AirForceGeneral" );
	if ( asciiEqualsNoCase( mapKey, "laser" ) )
		return AsciiString( "GC_LaserGeneral" );
	if ( asciiEqualsNoCase( mapKey, "superweapon" ) )
		return AsciiString( "GC_SuperweaponGeneral" );
	if ( asciiEqualsNoCase( mapKey, "tank" ) )
		return AsciiString( "GC_TankGeneral" );
	if ( asciiEqualsNoCase( mapKey, "nuke" ) )
		return AsciiString( "GC_NukeGeneral" );
	if ( asciiEqualsNoCase( mapKey, "stealth" ) )
		return AsciiString( "GC_StealthGeneral" );
	if ( asciiEqualsNoCase( mapKey, "toxin" ) )
		return AsciiString( "GC_ToxinGeneral" );
	if ( asciiEqualsNoCase( mapKey, "boss" ) )
		return AsciiString( "GC_BossGeneral" );
	return AsciiString::TheEmptyString;
}

Bool ArchipelagoSlotData::loadFromFile(
	const AsciiString& filePath,
	const AsciiString& expectedHash,
	Int expectedVersion,
	const AsciiString& inboundSeedId,
	const AsciiString& inboundSlotName,
	const AsciiString& inboundSessionNonce,
	AsciiString& errorMessage )
{
	reset();
	m_slotDataPath = filePath;
	m_slotDataHash = expectedHash;

	if ( expectedVersion != kExpectedSlotDataVersion )
	{
		errorMessage.format( "unsupported slotDataVersion %d", expectedVersion );
		return FALSE;
	}
	if ( expectedHash.isEmpty() || !startsWith( toLowerCopy( expectedHash.str() ), "sha256:" ) )
	{
		errorMessage = "missing or invalid slotDataHash";
		return FALSE;
	}

	AsciiString actualHash;
	if ( !computeFileSha256( filePath, actualHash ) )
	{
		errorMessage.format( "slot-data file not readable: %s", filePath.str() );
		return FALSE;
	}
	if ( actualHash.compareNoCase( expectedHash ) != 0 )
	{
		errorMessage.format( "slot-data hash mismatch expected=%s actual=%s", expectedHash.str(), actualHash.str() );
		return FALSE;
	}

	std::vector<unsigned char> bytes;
	if ( !readFileBytes( filePath, bytes ) )
	{
		errorMessage.format( "slot-data file not readable: %s", filePath.str() );
		return FALSE;
	}
	std::string content( bytes.begin(), bytes.end() );

	JsonValue root;
	std::string parseError;
	JsonParser parser( content );
	if ( !parser.parse( root, parseError ) || root.type != JsonValue::JSON_OBJECT )
	{
		errorMessage.format( "slot-data JSON parse failed: %s", parseError.c_str() );
		return FALSE;
	}

	std::string error;
	if ( !readRequiredInt( root, "version", m_version, error ) )
	{
		errorMessage = error.c_str();
		return FALSE;
	}
	if ( m_version != kExpectedSlotDataVersion )
	{
		errorMessage.format( "slot-data version mismatch %d", m_version );
		return FALSE;
	}
	if ( !readRequiredString( root, "logicModel", m_logicModel, error )
		|| !readRequiredString( root, "seedId", m_seedId, error )
		|| !readRequiredString( root, "slotName", m_slotName, error )
		|| !readRequiredString( root, "sessionNonce", m_sessionNonce, error ) )
	{
		errorMessage = error.c_str();
		return FALSE;
	}
	if ( m_logicModel.compareNoCase( kExpectedLogicModel ) != 0 )
	{
		errorMessage.format( "slot-data logicModel mismatch: %s", m_logicModel.str() );
		return FALSE;
	}
	if ( inboundSeedId.isNotEmpty() && m_seedId.compare( inboundSeedId ) != 0 )
	{
		errorMessage = "slot-data seedId does not match inbound";
		return FALSE;
	}
	if ( inboundSlotName.isNotEmpty() && m_slotName.compare( inboundSlotName ) != 0 )
	{
		errorMessage = "slot-data slotName does not match inbound";
		return FALSE;
	}
	if ( inboundSessionNonce.isNotEmpty() && m_sessionNonce.compare( inboundSessionNonce ) != 0 )
	{
		errorMessage = "slot-data sessionNonce does not match inbound";
		return FALSE;
	}

	const JsonValue* maps = root.get( "maps" );
	if ( maps == NULL || maps->type != JsonValue::JSON_OBJECT )
	{
		errorMessage = "slot-data missing maps object";
		return FALSE;
	}

	for ( std::map<std::string, JsonValue>::const_iterator mapIt = maps->objectValue.begin(); mapIt != maps->objectValue.end(); ++mapIt )
	{
		const JsonValue& mapObj = mapIt->second;
		if ( mapObj.type != JsonValue::JSON_OBJECT )
			continue;

		ArchipelagoSlotMap mapData;
		mapData.mapKey = AsciiString( mapIt->first.c_str() );
		mapData.mapLeafName = mapLeafNameForKey( mapData.mapKey );
		if ( mapData.mapLeafName.isEmpty() )
			continue;
		if ( !readRequiredInt( mapObj, "mapSlot", mapData.mapSlot, error ) )
		{
			errorMessage = error.c_str();
			return FALSE;
		}

		const JsonValue* mission = mapObj.get( "missionVictory" );
		if ( mission == NULL || mission->type != JsonValue::JSON_OBJECT )
		{
			errorMessage.format( "%s missing missionVictory", mapData.mapKey.str() );
			return FALSE;
		}
		if ( !readRequiredString( *mission, "runtimeKey", mapData.missionRuntimeKey, error )
			|| !readRequiredInt( *mission, "apLocationId", mapData.missionApLocationId, error ) )
		{
			errorMessage = error.c_str();
			return FALSE;
		}
		if ( !m_runtimeKeys.insert( mapData.missionRuntimeKey ).second )
		{
			errorMessage.format( "duplicate runtime key: %s", mapData.missionRuntimeKey.str() );
			return FALSE;
		}
		m_missionRuntimeKeys.insert( mapData.missionRuntimeKey );

		const JsonValue* clusters = mapObj.get( "clusters" );
		if ( clusters == NULL || clusters->type != JsonValue::JSON_ARRAY )
		{
			errorMessage.format( "%s missing clusters array", mapData.mapKey.str() );
			return FALSE;
		}
		for ( size_t clusterIndex = 0; clusterIndex < clusters->arrayValue.size(); ++clusterIndex )
		{
			const JsonValue& clusterObj = clusters->arrayValue[clusterIndex];
			if ( clusterObj.type != JsonValue::JSON_OBJECT )
			{
				errorMessage.format( "%s cluster is not object", mapData.mapKey.str() );
				return FALSE;
			}
			ArchipelagoSlotCluster cluster;
			if ( !readRequiredString( clusterObj, "clusterKey", cluster.clusterKey, error )
				|| !readRequiredString( clusterObj, "tier", cluster.tier, error )
				|| !readRequiredString( clusterObj, "clusterClass", cluster.clusterClass, error )
				|| !readRequiredString( clusterObj, "primaryRequirement", cluster.primaryRequirement, error )
				|| !readRequiredString( clusterObj, "requiredMissionGate", cluster.requiredMissionGate, error ) )
			{
				errorMessage = error.c_str();
				return FALSE;
			}

			const JsonValue* center = clusterObj.get( "center" );
			if ( center == NULL || center->type != JsonValue::JSON_OBJECT
				|| !readRequiredReal( *center, "x", cluster.center.x, error )
				|| !readRequiredReal( *center, "y", cluster.center.y, error )
				|| !readRequiredReal( *center, "radius", cluster.radius, error ) )
			{
				errorMessage = center == NULL ? "cluster missing center" : error.c_str();
				return FALSE;
			}
			cluster.center.z = 0.0f;

			const JsonValue* units = clusterObj.get( "units" );
			if ( units == NULL || units->type != JsonValue::JSON_ARRAY || units->arrayValue.empty() )
			{
				errorMessage.format( "%s.%s missing units", mapData.mapKey.str(), cluster.clusterKey.str() );
				return FALSE;
			}
			for ( size_t unitIndex = 0; unitIndex < units->arrayValue.size(); ++unitIndex )
			{
				const JsonValue& unitObj = units->arrayValue[unitIndex];
				if ( unitObj.type != JsonValue::JSON_OBJECT )
				{
					errorMessage.format( "%s.%s unit is not object", mapData.mapKey.str(), cluster.clusterKey.str() );
					return FALSE;
				}
				ArchipelagoSlotUnit unit;
				if ( !readRequiredString( unitObj, "unitKey", unit.unitKey, error )
					|| !readRequiredString( unitObj, "runtimeKey", unit.runtimeKey, error )
					|| !readRequiredInt( unitObj, "apLocationId", unit.apLocationId, error )
					|| !readRequiredString( unitObj, "defenderTemplate", unit.defenderTemplate, error ) )
				{
					errorMessage = error.c_str();
					return FALSE;
				}
				readOptionalString( unitObj, "displayName", unit.displayName );
				if ( !m_runtimeKeys.insert( unit.runtimeKey ).second )
				{
					errorMessage.format( "duplicate runtime key: %s", unit.runtimeKey.str() );
					return FALSE;
				}
				cluster.units.push_back( unit );
			}
			mapData.clusters.push_back( cluster );
		}

		const JsonValue* capturedBuildings = mapObj.get( "capturedBuildings" );
		if ( capturedBuildings != NULL )
		{
			if ( capturedBuildings->type != JsonValue::JSON_ARRAY )
			{
				errorMessage.format( "%s capturedBuildings is not array", mapData.mapKey.str() );
				return FALSE;
			}
			for ( size_t capturedIndex = 0; capturedIndex < capturedBuildings->arrayValue.size(); ++capturedIndex )
			{
				const JsonValue& capturedObj = capturedBuildings->arrayValue[capturedIndex];
				if ( capturedObj.type != JsonValue::JSON_OBJECT )
				{
					errorMessage.format( "%s captured building is not object", mapData.mapKey.str() );
					return FALSE;
				}
				ArchipelagoSlotCapturedBuilding captured;
				if ( !readRequiredString( capturedObj, "buildingKey", captured.buildingKey, error )
					|| !readRequiredString( capturedObj, "runtimeKey", captured.runtimeKey, error )
					|| !readRequiredInt( capturedObj, "apLocationId", captured.apLocationId, error )
					|| !readRequiredString( capturedObj, "label", captured.label, error ) )
				{
					errorMessage = error.c_str();
					return FALSE;
				}
				readOptionalString( capturedObj, "template", captured.templateName );
				readOptionalString( capturedObj, "authorStatus", captured.authorStatus );
				if ( !m_runtimeKeys.insert( captured.runtimeKey ).second )
				{
					errorMessage.format( "duplicate runtime key: %s", captured.runtimeKey.str() );
					return FALSE;
				}
				mapData.capturedBuildings.push_back( captured );
			}
		}

		const JsonValue* supplyPileThresholds = mapObj.get( "supplyPileThresholds" );
		if ( supplyPileThresholds != NULL )
		{
			if ( supplyPileThresholds->type != JsonValue::JSON_ARRAY )
			{
				errorMessage.format( "%s supplyPileThresholds is not array", mapData.mapKey.str() );
				return FALSE;
			}
			for ( size_t thresholdIndex = 0; thresholdIndex < supplyPileThresholds->arrayValue.size(); ++thresholdIndex )
			{
				const JsonValue& thresholdObj = supplyPileThresholds->arrayValue[thresholdIndex];
				if ( thresholdObj.type != JsonValue::JSON_OBJECT )
				{
					errorMessage.format( "%s supply pile threshold is not object", mapData.mapKey.str() );
					return FALSE;
				}
				ArchipelagoSlotSupplyPileThreshold threshold;
				if ( !readRequiredString( thresholdObj, "pileKey", threshold.pileKey, error )
					|| !readRequiredString( thresholdObj, "thresholdKey", threshold.thresholdKey, error )
					|| !readRequiredString( thresholdObj, "runtimeKey", threshold.runtimeKey, error )
					|| !readRequiredInt( thresholdObj, "apLocationId", threshold.apLocationId, error )
					|| !readRequiredString( thresholdObj, "label", threshold.label, error ) )
				{
					errorMessage = error.c_str();
					return FALSE;
				}
				readOptionalString( thresholdObj, "template", threshold.templateName );
				readOptionalString( thresholdObj, "authorStatus", threshold.authorStatus );
				if ( !readOptionalInt( thresholdObj, "startingAmount", threshold.startingAmount, threshold.hasStartingAmount )
					|| !readOptionalInt( thresholdObj, "amountCollected", threshold.amountCollected, threshold.hasAmountCollected )
					|| !readOptionalReal( thresholdObj, "fractionCollected", threshold.fractionCollected, threshold.hasFractionCollected ) )
				{
					errorMessage.format( "%s supply pile threshold has invalid numeric field", mapData.mapKey.str() );
					return FALSE;
				}
				if ( !threshold.hasAmountCollected && !threshold.hasFractionCollected )
				{
					errorMessage.format( "%s.%s.%s missing threshold amount/fraction", mapData.mapKey.str(), threshold.pileKey.str(), threshold.thresholdKey.str() );
					return FALSE;
				}
				if ( !m_runtimeKeys.insert( threshold.runtimeKey ).second )
				{
					errorMessage.format( "duplicate runtime key: %s", threshold.runtimeKey.str() );
					return FALSE;
				}
				mapData.supplyPileThresholds.push_back( threshold );
			}
		}

		m_maps.push_back( mapData );
	}

	if ( m_maps.empty() )
	{
		errorMessage = "slot-data contained no known maps";
		return FALSE;
	}

	m_loaded = TRUE;
	return TRUE;
}

Int ArchipelagoSlotData::getFutureLocationCount() const
{
	Int count = 0;
	for ( size_t i = 0; i < m_maps.size(); ++i )
	{
		count += static_cast<Int>( m_maps[i].capturedBuildings.size() );
		count += static_cast<Int>( m_maps[i].supplyPileThresholds.size() );
	}
	return count;
}

const ArchipelagoSlotMap* ArchipelagoSlotData::findMapByKey( const AsciiString& mapKey ) const
{
	for ( size_t i = 0; i < m_maps.size(); ++i )
	{
		if ( m_maps[i].mapKey.compareNoCase( mapKey ) == 0 )
			return &m_maps[i];
	}
	return NULL;
}

const ArchipelagoSlotMap* ArchipelagoSlotData::findMapByLeafName( const AsciiString& mapLeafName ) const
{
	for ( size_t i = 0; i < m_maps.size(); ++i )
	{
		if ( m_maps[i].mapLeafName.compareNoCase( mapLeafName ) == 0 )
			return &m_maps[i];
	}
	return NULL;
}

AsciiString ArchipelagoSlotData::getMissionRuntimeKeyForGeneralIndex( Int generalIndex ) const
{
	const AsciiString mapKey = mapKeyForGeneralIndex( generalIndex );
	if ( mapKey.isEmpty() )
		return AsciiString::TheEmptyString;
	const ArchipelagoSlotMap* mapData = findMapByKey( mapKey );
	return mapData != NULL ? mapData->missionRuntimeKey : AsciiString::TheEmptyString;
}

Bool ArchipelagoSlotData::isSelectedRuntimeKey( const AsciiString& runtimeKey ) const
{
	return m_runtimeKeys.find( runtimeKey ) != m_runtimeKeys.end();
}

Bool ArchipelagoSlotData::isMissionRuntimeKey( const AsciiString& runtimeKey ) const
{
	return m_missionRuntimeKeys.find( runtimeKey ) != m_missionRuntimeKeys.end();
}
